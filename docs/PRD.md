# PRD: Safe to Bill?

**One line:** before an urgent care claim leaves the clinic, check whether the visit note supports
the E/M level being billed, and bill only the claims that are safe; hold the rest for a coder with
the reason and the note's own words.

## Problem

- Payers are denying and downcoding more urgent care claims. Trade coverage in 2026 reports more
  E/M downcoding by commercial payers and a rise in diagnosis-based denials (UrgentIQ, June 2026;
  vendor content, so directional).
- The E/M level is the biggest single line on most urgent care claims, and it is set by the
  documentation: the AMA's medical decision making (MDM) table. A level the note does not support
  is a denial, a downcode or an audit finding. A level below what the note supports is revenue
  the clinic earned and did not collect.
- Platforms are moving to autonomous coding. Experity, which says nearly half of US urgent care
  clinics use its platform, acquired Exdion Healthcare on 1 July 2026; Exdion "processes most
  patient visits without manual intervention using machine learning and automated workflows"
  (JUCM, 7 July 2026). Experity cites an 86% reduction in claim denials for organisations using
  the combined technology (company claim).
- The hard part of autonomous coding is not producing a code. It is knowing **which claims are
  safe to send with no human touch**, and proving it on data the system has never seen.

## Users

- **Coder / biller** at an urgent care group: wants only the claims that need a human, each with
  the reason, instead of reviewing every chart.
- **Revenue cycle lead:** wants fewer denials and downcodes without hiring more coders, and an
  audit trail for every automated claim.
- **Clinician:** wants to know what their note was missing when a level is held, in their own words.

## What it does

Input: the visit note, new or established patient, the billed office/outpatient E/M code
(99202-99205, 99212-99215).

1. Extract the MDM elements (problems addressed, data reviewed, risk of management), each with the
   exact words from the note that support it.
2. Verify every quote against the note in code. An element whose quote is not in the note is dropped.
3. Compute the supported level with a deterministic engine (the AMA table: 2 of 3 elements).
4. Decide:
   - **BILL** when the billed code equals the supported code and the extraction is confident.
   - **HOLD** otherwise, with a reason: overcoded (denial and audit risk), undercoded (revenue left
     behind), or not confident (needs a coder).

Output: the decision, the supported code, each element's level and the quotes behind it.

## Non-goals

- Coding by total time, procedures, modifiers, ICD-10 specificity, payer-specific edits
  (urgent care S-codes, a payer's own downcoding policy). The first version checks one thing: does
  the documentation support the E/M level.
- Choosing a code for the clinician. It checks the billed code; the supported code is shown as evidence.
- Real patient data. Everything here is synthetic.

## Approach and baselines

Three pipelines are scored on the same notes, so the value of each layer is measured, not assumed:

- **A. Rules:** keyword and pattern extraction plus the deterministic engine.
- **B. Classic ML:** TF-IDF + logistic regression trained on generated notes to predict the level
  directly, with a probability threshold as its confidence gate (tuned on generated dev data).
- **C. LLM extraction (what ships):** an LLM extracts elements with quotes, code verifies the quotes,
  the engine computes the level, and **two independent runs must agree** or the claim is held.
- **C1:** C with a single run, to measure what the second run adds.

## Success metrics

North star: **share of correctly coded claims billed with no human touch, at zero wrong auto-bills.**

A **wrong auto-bill** is a BILL decision on a claim whose billed code is not the code the note
supports (by the hand label). It is the costly error: an automated denial, downcode or audit finding.

## Release gate (written before any held-out run)

On the 36-note held-out set, run once with the frozen configuration:

| Metric | Bar |
|---|---|
| Wrong auto-bills | **0** |
| Overcoded claims held (of 12) | **at least 11** |
| Correctly coded claims auto-billed (of 19) | **at least 50%** (10 or more) |
| Quotes shown that are not in the note | **0** |

36 notes cannot prove a low error rate: 0 wrong out of about 15 auto-bills still leaves a 95%
upper bound near 20%. The run reports Wilson intervals, and a pass means "ready for a larger
shadow test", not "ready for production".

## Evaluation data

- `data/handwritten/dev.json`: 12 notes, used to develop rules and the prompt.
- `data/handwritten/holdout.json`: 36 notes (19 correctly billed, 12 overcoded, 5 undercoded),
  frozen with SHA-256 hashes in `docs/FREEZE.md` before any rule, model or prompt read them. Run once.
- `data/generated/`: seeded template notes with labels by construction, for training B and for
  regression tests. They are easy by design; the hand-written sets are the real test.

All notes were written with Claude Code and labelled against `docs/LABELLING.md`.
**No certified coder has reviewed the labels**; that is the first thing a real pilot needs.

## Risks

- **Label error** is the biggest risk: the bar is only as good as the answer key.
- Over-automation: a confident wrong extraction bills a wrong level. Mitigations: quote checks,
  two runs that must agree, and a deterministic engine so the model never picks the code.
- Synthetic notes are cleaner than real ones (templates, copy-forward text, scribe output).
- Privacy in production: notes are PHI. The API logs a hash of the note, never its text.

## Rollout (if this were a product)

1. Shadow mode on real claims with coders' final codes as labels; publish the agreement.
2. Auto-bill only for the visit types and payers where shadow mode showed zero wrong auto-bills.
3. Monitor weekly: hold rate, overcode catches, and denial reason codes from the payer's 835
   remittance per payer, with an alert when a payer's denial rate moves.
