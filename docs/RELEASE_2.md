# Release run 2: plan and gate

Written before release run 2, with its notes frozen and pushed to GitHub before any rule, model
or prompt read them.

## Why a second run

Release run 1 (36 held-out notes) passed the gate, but it left two problems:

1. **Quote stitching.** In 3 notes the model joined two non-adjacent sentences into one quote. The
   verifier rejected the quote, the problem it supported was dropped, and the claim was held:
   safe, but 3 correct claims went to a coder. The verifier now accepts a quote made of whole
   sentences from the note, in order, each at least 3 words. Re-scoring run 1's cached answers
   with the fix gives 36/36 levels and 19/19 correct claims auto-billed, **post hoc**: the fix was
   designed after seeing those failures, so that number is not evidence.
2. **The rules baseline saw the test.** Its rule patterns were written while reading the run-1
   notes, so its 100% says nothing.

Run 2 tests the fixed system, and gives the rules a fair test, on 24 notes no rule, model or
prompt has read.

## What is frozen

- `data/handwritten/holdout2.json`: 24 notes, labelled against `docs/LABELLING.md`: 12 correctly
  billed, 7 overcoded, 5 undercoded. Written in a messier style than run 1 (history carried
  forward and not addressed, a test whose interpretation is billed separately, IM morphine, care
  limited by social determinants, a confused patient's daughter giving the history, a phone call
  with a pulmonologist).
- Configuration: prompt v1, `gemini-3.1-flash-lite`, temperature 1.0, two runs must agree, the
  fixed verifier, ML threshold 0.92. No other change since run 1.

Same author as before: the notes were written by Claude Code, which also wrote the rules and the
prompt. They were not checked against the rules or the prompt while being written.

## Gate (same bars as run 1)

| Metric | Bar |
|---|---|
| Wrong auto-bills | **0** |
| Overcoded claims held (of 7) | **at least 6** |
| Correctly coded claims auto-billed (of 12) | **at least 50%** (6 or more) |
| Quotes shown that are not in the note | **0** |

Run once: `python -m eval.run_eval --split holdout2 --pipelines rules,ml,llm,llm1 --release`.
