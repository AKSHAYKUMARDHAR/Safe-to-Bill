# Safe to Bill?

**Before an urgent care claim goes out, check whether the visit note supports the E/M level being
billed. Bill only the claims that are safe; hold the rest for a coder, with the reason and the
note's own words.**

**Status:** the shipped pipeline (LLM extraction + code checks + a deterministic AMA engine)
**passed its release gate** on its first and only run on 36 held-out notes: **0 wrong auto-bills
in 16**, all 12 overcoded and all 5 undercoded claims held, 16 of 19 correctly coded claims billed
with no human touch. 36 synthetic notes are a small test: 0 in 16 still leaves a 95% upper bound of
19% on the wrong-bill rate, so a pass means "ready for a larger shadow test", not "ready for
production". Details and caveats below.

## Why

- Payers are denying and downcoding more urgent care claims; trade coverage in 2026 reports more
  E/M downcoding by commercial payers ([UrgentIQ](https://urgentiq.com/iq-boost/the-hidden-revenue-drain-how-commercial-payers-are-downcoding-more-claims), vendor content).
- The E/M level is set by the documentation, through the AMA's medical decision making (MDM)
  table. A level the note does not support is a denial, a downcode or an audit finding; a level
  below it is revenue the clinic earned and did not collect.
- Revenue cycle platforms are moving to autonomous coding, for example Experity's July 2026
  acquisition of Exdion, whose software "processes most patient visits without manual intervention"
  ([JUCM](https://www.jucm.com/experity-acquisition-of-exdion-healthcare-brings-ai-automation-to-rcm/)).
  The hard part is knowing **which claims are safe to send with no human touch**, and proving it on
  notes the system has never seen. That is what this project measures.

Independent project, not affiliated with any company named here. All notes are synthetic.

## How it works

```
visit note + patient type + billed code
   |
   |-- LLM extracts MDM elements (problems, data, risk), each with an exact quote   (prompts/extract_v1.md)
   |-- code drops any element whose quote is not in the note                        (safe_to_bill/verify.py)
   |-- deterministic engine: AMA table, 2 of 3 elements -> level -> code            (safe_to_bill/mdm.py)
   |-- a second, independent reading must reach the same level, or the claim is held
   v
BILL  only when billed code == supported code and the check is confident
HOLD  overcoded (denial / audit risk) | undercoded (revenue left behind) | needs a coder (why)
```

The model never picks the code: it reads, code checks and decides. Every element shown to a coder
carries the note's own words, checked character for character.

Three pipelines are scored on the same notes so each layer's value is measured:

| | Pipeline | What it is |
|---|---|---|
| A | `rules` | keyword and pattern extraction + the same engine (deterministic baseline) |
| B | `ml` | TF-IDF + logistic regression trained on 800 generated notes, predicting the level directly; probability threshold 0.92 (tuned on generated dev) as its confidence gate |
| C | `llm` | **ships**: Gemini (`gemini-3.1-flash-lite`, free tier) extraction + quote checks + engine, two runs must agree |
| C1 | `llm1` | C with one run, to measure what the second run adds |

## Results

### Release run: 36 held-out notes, run once (`eval/runs/20261120T093230_holdout_release.json`)

19 correctly billed, 12 overcoded, 5 undercoded. Gate (written in the PRD before the run): 0 wrong
auto-bills, at least 11 of 12 overcoded held, at least 50% of correct claims auto-billed, 0 quotes
not in the note.

| Pipeline | Level accuracy | Auto-bills | Wrong auto-bills (95% CI) | Correct claims auto-billed | Overcoded held | Undercoded held | Gate |
|---|---|---|---|---|---|---|---|
| A rules* | 100% | 19 | 0 (0-17%) | 19/19 | 12/12 | 5/5 | pass* |
| B ml | 75% | 5 | 0 (0-43%) | 5/19 | 12/12 | 5/5 | **fail** |
| **C llm (ships)** | **94%** | **16** | **0 (0-19%)** | **16/19** | **12/12** | **5/5** | **pass** |
| C1 llm, one run | 94% | 17 | 0 (0-18%) | 17/19 | 12/12 | 5/5 | pass |

\* **The rules result is not evidence.** I wrote the rule patterns in the same session as the
held-out notes and checked their wording against those notes while writing them. Treat A as an
upper bound for a baseline that has seen the test, not as a fair comparison.

### Dev runs (12 hand-written notes; 30 generated notes)

| Pipeline | Hand-written dev level acc | Auto-billed / correct | Generated dev level acc |
|---|---|---|---|
| A rules | 100% (also written against these notes) | 6/6 | 97% |
| B ml | 67% | 2/6 | 77% (86% on all 200) |
| C llm | 100% | 5/6 | 80% |

No rule, prompt or threshold was changed after any of these runs. Prompt v1 is the only prompt.

## What the results say

1. **The shipped pipeline never auto-billed a wrong level** in 16 held-out auto-bills (and 5 on dev).
   It held every overcoded claim; 10 of the 12 were held as "overcoded" with the right supported
   code, and 2 as "needs a coder". When it held an overcoded or undercoded claim, the supported
   code it showed was right in 16 of 17.
2. **Every miss was a safe one, and the commonest cause was quote stitching.** In 3 held-out notes
   (H19, H35, H36) the model's quote for the problem joined the patient's first sentence to the
   assessment line, skipping the text between them. The verifier rejected the quote, so no
   problem survived and the claim was held. That cost 2 of the 3 correct claims it did not bill
   (H19, H36); the third (H23) was the two readings disagreeing. The check did its job: an
   unverifiable reading is never billed.
3. **The second reading has not earned its cost yet.** Across all 48 hand-written notes the
   single-run pipeline (C1) also made 0 wrong auto-bills; the second run held 2 claims that C1
   billed correctly (D08, H23) and caught nothing. It stays in for now, because 48 notes cannot
   show that a safety check is unnecessary, and it is the first thing the larger test should
   measure. (Same lesson as my scam checker, where a third model run never changed a verdict.)
4. **The classic ML baseline learned the template, not the rules.** Trained on generated notes,
   it predicted 75% of hand-written levels; its probability gate kept it safe (0 wrong) but it billed
   only 5 of 19 correct claims, failing the automation bar. E/M levels come from counting and
   combining elements, which a bag-of-words classifier does not do; extracting elements and letting
   code apply the AMA table generalises better on notes it has not seen.
5. **Element errors** (shipped pipeline, run 1 vs labels): problems 33/36 (the 3 stitched quotes),
   data 35/36, risk 32/36. None changed a billing decision in the wrong direction.

## Caveats

- **Synthetic notes, written and labelled with Claude Code** against `docs/LABELLING.md`. **No
  certified coder has reviewed the labels**; that is the first thing a real pilot needs.
- **Same author for notes, rules and prompt.** The held-out notes were frozen (SHA-256 in
  `docs/FREEZE.md`) before any rule, model or prompt ran on them, but the rules were written while
  reading them (see the table note) and the prompt was written by the same author.
- **Small:** 36 held-out notes cannot measure a low error rate; Wilson intervals are reported.
- **Scope:** office/outpatient E/M by MDM only. Not covered: time-based coding, procedures and
  modifiers, ICD-10 specificity, payer-specific rules such as urgent care S-codes.
- Real notes are messier than these (copy-forward text, scribe output, templates).

## Next steps

1. Fix quote stitching: ask for one contiguous span per quote, or verify a multi-sentence quote as
   ordered fragments. Any re-score of the held-out answers will be labelled post hoc.
2. Labels from a certified coder, and 100+ fresh notes for a second release run.
3. Shadow mode on real claims with coders' final codes as labels; monitor holds, overcode catches
   and payer denial reason codes (835 remittance) weekly, per payer.

## Run it

```bash
python -m venv .venv && .venv/Scripts/activate        # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env                                   # add GEMINI_API_KEY for the LLM pipeline

python -m safe_to_bill.generator                       # 1,000 generated notes (seed 7)
python -m safe_to_bill.ml_baseline                     # trains B, tunes its threshold
pytest -q                                              # 69 offline tests (the LLM is faked)
python -m eval.run_eval --split dev --pipelines rules,ml,llm,llm1   # re-scores from the answer cache

uvicorn api.main:app --reload                          # POST /check, GET /stats, GET /health
docker build -t safe-to-bill . && docker run -p 8000:8000 --env-file .env safe-to-bill
```

```bash
curl -X POST localhost:8000/check -H "Content-Type: application/json" -d '{
  "note": "55F ran out of amlodipine. Hypertension, stable, BP 128/78.\nAssessment: essential hypertension, stable.\nPlan: refilled amlodipine 5 mg daily.",
  "patient_type": "established", "billed_code": "99214"}'
# -> HOLD, overcoded: the note supports 99213 (one stable chronic illness + a refill)
```

The API logs a SHA-256 of each note, never its text. Model answers used in evaluation are cached in
`eval/cache/` (keyed by model, prompt version, run and note), so every run can be re-scored for free.
CI runs the tests, re-scores the dev set from that cache with no API key, and builds the Docker image.

## Repo map

| Path | What |
|---|---|
| `docs/PRD.md` | problem, users, metrics, release gate (written before the held-out run) |
| `docs/LABELLING.md` | the AMA MDM table as a labelling guide, with judgement calls |
| `docs/FREEZE.md` | SHA-256 of the frozen data, guide, prompt and code before the release run |
| `data/handwritten/` | 12 dev + 36 held-out notes with element-level labels |
| `safe_to_bill/` | engine, rules, LLM extractor, quote verifier, decision, ML baseline, generator |
| `eval/` | evaluation harness, per-note results, run logs, model answer cache |
| `api/` | FastAPI service |
