# Safe to Bill?

**Before an urgent care claim goes out, check whether the visit note supports the E/M level being
billed. Bill only the claims that are safe; hold the rest for a coder, with the reason and the
note's own words.**

**Status: blocked by its own release gate.** Release run 1 (36 held-out notes) passed: 0 wrong
auto-bills in 16. Release run 2, on 24 fresh notes frozen and pushed before the run, **failed: 2
wrong auto-bills in 13**. In both failures the two independent readings made the *same* mistake, so
the agreement check could not catch it. That is the main finding, and the next version has to
answer it. **[Explore every held-out note, decision and quote](https://akshaykumardhar.github.io/Safe-to-Bill/)**.

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

| | Pipeline | What it is |
|---|---|---|
| A | `rules` | keyword and pattern extraction + the same engine (deterministic baseline) |
| B | `ml` | TF-IDF + logistic regression trained on 800 generated notes, predicting the level directly; probability threshold 0.92 (tuned on generated dev) as its confidence gate |
| C | `llm` | **ships**: Gemini (`gemini-3.1-flash-lite`, free tier) extraction + quote checks + engine, two runs must agree |
| C1 | `llm1` | C with one run, to measure what the second run adds |

Quote verifier versions: **v1** exact quotes (release run 1); **v2** also accepts whole sentences
stitched together in order (release run 2); **v3** also drops a problem quoted from a
past-history line or marked "not addressed" (after run 2; post hoc only so far).

## Results

Gate (PRD, written before run 1): 0 wrong auto-bills; all but one overcoded claim held; at least
50% of correctly coded claims auto-billed; 0 quotes not in the note. A **wrong auto-bill** is a
BILL on a claim whose billed code is not the code the note supports (by the hand label).

### Release run 2: 24 fresh notes, run once, verifier v2 (`eval/runs/20261120T103455_holdout2_release.json`)

12 correctly billed, 7 overcoded, 5 undercoded. Frozen and pushed at commit `c4bebe4` before the run.

| Pipeline | Level accuracy | Wrong auto-bills (95% CI) | Correct claims auto-billed | Overcoded held | Undercoded held | Gate |
|---|---|---|---|---|---|---|
| **C llm (ships)** | 83% | **2 of 13 (4-42%)** | 11/12 | 6/7 | 4/5 | **fail** |
| C1 llm, one run | 83% | 2 of 13 | 11/12 | 6/7 | 4/5 | fail |
| A rules | 83% | 1 of 11 | 10/12 | 6/7 | 5/5 | fail |
| B ml | 67% | 0 of 0 | 0/12 | 7/7 | 5/5 | fail |
| *C with verifier v3, post hoc* | *88%* | *1 of 12* | *11/12* | *7/7* | *4/5* | *fail* |

### Release run 1: 36 held-out notes, run once, verifier v1 (`eval/runs/20261120T093230_holdout_release.json`)

19 correctly billed, 12 overcoded, 5 undercoded.

| Pipeline | Level accuracy | Wrong auto-bills (95% CI) | Correct claims auto-billed | Overcoded held | Undercoded held | Gate |
|---|---|---|---|---|---|---|
| **C llm (ships)** | 94% | **0 of 16 (0-19%)** | 16/19 | 12/12 | 5/5 | **pass** |
| C1 llm, one run | 94% | 0 of 17 | 17/19 | 12/12 | 5/5 | pass |
| A rules* | 100% | 0 of 19 | 19/19 | 12/12 | 5/5 | pass* |
| B ml | 75% | 0 of 5 | 5/19 | 12/12 | 5/5 | fail |
| *C with verifier v2 or v3, post hoc* | *100%* | *0 of 19* | *19/19* | *12/12* | *5/5* | *pass* |

\* I wrote the rule patterns while reading these 36 notes, so A's run-1 score is not evidence.
Run 2 is its fair test. Per-note results for run 1 were regenerated from the answer cache with
verifier v1 and match the logged run exactly (`holdout_release-reproduced`); run 2 likewise
(`holdout2_rescore-v2`).

## What the results say

1. **Agreement between two readings of the same model is not independence.** All four of the
   shipped pipeline's misses in run 2 had both readings agreeing on the wrong answer. Across all
   72 hand-written notes the second reading never prevented a wrong bill; the only claims it held
   were 2 correct ones where the readings happened to vary (D08, H23).
2. **Copy-forward history caused an overcoded claim to go out (R11).** Both readings counted three
   chronic conditions from a past-medical-history line that itself says "not addressed today",
   and the note was billed one level too high. This is the pattern payer audits look for. Verifier
   v3 drops problems quoted from history lines; post hoc, R11 is held as overcoded.
3. **A low-risk plan read as minimal let an undercoded claim go out (R16).** "Artificial tears OTC"
   was rated minimal risk by both readings; the wrong level happened to equal the billed code.
   Not fixed: one note is not a reason to change a rule, and fixing it against the test would be
   fitting to it.
4. **Holds need correct reasons too (R10).** Urosepsis with low blood pressure was read as
   moderate instead of a threat to life. The claim was held, which is safe for billing, but the
   hold said "overcoded, supports 99204": a coder who trusted it would downcode a correct claim.
5. **Stitched quotes (run 1)** made 3 safe holds; verifier v2 fixed them post hoc. One survives in
   run 2 (R15): the stitched piece "A/P: anaphylaxis." has 2 words, under the 3-word minimum,
   so the claim was held.
6. **The rules baseline, tested fairly, also failed** (R01: it auto-billed an overcoded common cold;
   threats not on its word list, such as torsion and cauda equina, were held). **The ML baseline
   learned the generator's templates**: it auto-billed nothing in run 2.

## Caveats

- **Synthetic notes, written and labelled with Claude Code** against `docs/LABELLING.md`. **No
  certified coder has reviewed the labels**; that is the first thing a real pilot needs. Held-out
  labels are never changed after a run.
- **Same author for notes, rules and prompt.** Run 2's notes were not checked against the rules
  or prompt while being written, but they share an author.
- **Small:** 60 held-out notes in two runs cannot measure a low error rate; Wilson intervals are reported.
- **Scope:** office/outpatient E/M by MDM only. Not covered: time-based coding, procedures and
  modifiers, ICD-10 specificity, payer-specific rules such as urgent care S-codes.

## Next steps

1. **An independent second opinion**, not a second reading of the same model: a different model
   family, or the rules engine as a floor for risk (an "OTC" plan is at least low risk), so that
   a systematic misreading has to fool two different readers.
2. Severity checks from structured data (vital signs that signal instability) before a hold
   suggests a downcode.
3. Labels from a certified coder, then 100+ fresh notes for release run 3 with v3 and the
   independent check.
4. Shadow mode on real claims with coders' final codes as labels; monitor holds, overcode catches
   and payer denial reason codes (835 remittance) weekly, per payer.

## Run it

```bash
python -m venv .venv && .venv/Scripts/activate        # Windows; source .venv/bin/activate elsewhere
pip install -r requirements.txt
cp .env.example .env                                   # add GEMINI_API_KEY for the LLM pipeline

python -m safe_to_bill.generator                       # 1,000 generated notes (seed 7)
python -m safe_to_bill.ml_baseline                     # trains B, tunes its threshold
pytest -q                                              # 97 offline tests (the LLM is faked)
python -m eval.run_eval --split dev --pipelines rules,ml,llm,llm1 --cache-only
python -m eval.run_eval --split holdout2 --pipelines rules,llm,llm1 --rescore --verifier v2   # reproduces run 2
python -m eval.build_site                              # rebuilds the explorer (docs/index.html)

uvicorn api.main:app --reload                          # POST /check, GET /stats, GET /health
docker build -t safe-to-bill . && docker run -p 8000:8000 --env-file .env safe-to-bill
```

```bash
curl -X POST localhost:8000/check -H "Content-Type: application/json" -d '{
  "note": "55F ran out of amlodipine. Hypertension, stable, BP 128/78.\nAssessment: essential hypertension, stable.\nPlan: refilled amlodipine 5 mg daily.",
  "patient_type": "established", "billed_code": "99214"}'
# -> HOLD, overcoded: the note supports 99213 (one stable chronic illness + a refill)
```

The API logs a SHA-256 of each note, never its text. Model answers are cached in `eval/cache/`
(keyed by model, prompt version, run and note), so every run can be re-scored for free and
re-scoring never calls the model. CI runs the tests, re-scores the dev set from the cache with no
API key, and builds the Docker image.

## Repo map

| Path | What |
|---|---|
| `docs/PRD.md` | problem, users, metrics, release gate (written before run 1) |
| `docs/RELEASE_2.md` | plan and gate for release run 2 (written before it) |
| `docs/LABELLING.md` | the AMA MDM table as a labelling guide, with judgement calls |
| `docs/FREEZE.md` | SHA-256 of the frozen notes, guide, prompt and code before each release run |
| `docs/index.html` | the results explorer, built by `eval/build_site.py` |
| `data/handwritten/` | 12 dev, 36 run-1 and 24 run-2 notes with element-level labels |
| `safe_to_bill/` | engine, rules, LLM extractor, quote verifier, decision, ML baseline, generator |
| `eval/` | evaluation harness, per-note results, run logs, model answer cache |
| `api/` | FastAPI service |

Notes, labels and code were written with Claude Code.
