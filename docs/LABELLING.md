# Labelling guide

Every note in `data/handwritten/` is labelled with this guide, by hand, before any model or rule
reads it. The engine in `safe_to_bill/mdm.py` implements the same table, so a label and a
prediction are always computed the same way from the same elements.

Source: the AMA CPT office or other outpatient E/M guidelines (2021, revised 2023), level of
medical decision making (MDM) table. This project codes **by MDM only**. Coding by total time is
out of scope (see the PRD).

## Codes

| MDM level | Level number | New patient | Established patient |
|---|---|---|---|
| Straightforward | 1 | 99202 | 99212 |
| Low | 2 | 99203 | 99213 |
| Moderate | 3 | 99204 | 99214 |
| High | 4 | 99205 | 99215 |

99211 (no MDM requirement) and the deleted 99201 are not used.

**The level is the highest level at which at least 2 of the 3 elements (problems, data, risk)
meet or exceed it.** Example: problems moderate, data minimal, risk moderate gives moderate.
Problems low, data minimal, risk moderate gives **low**: one moderate element is not enough.

## Element 1: number and complexity of problems addressed

Count only problems the clinician evaluated or treated at this visit.

| Type (`type` in the data) | Level |
|---|---|
| `self_limited_minor`: self-limited or minor problem (insect bite, abrasion, common cold, mild sunburn, splinter, skin tag) | 1 if one, **2 if two or more** |
| `acute_uncomplicated`: acute, uncomplicated illness or injury (strep or viral pharyngitis, sprain, cystitis, otitis media, conjunctivitis, uncomplicated gastroenteritis) | 2 |
| `stable_acute`: stable acute illness (acute problem already being treated, improving) | 2 |
| `stable_chronic`: stable chronic illness (at treatment goal) | 2 if one, **3 if two or more** |
| `chronic_exacerbation`: chronic illness with exacerbation, progression or side effects of treatment | 3 |
| `undiagnosed_uncertain`: undiagnosed new problem with uncertain prognosis (new mass or lump) | 3 |
| `acute_systemic`: acute illness with systemic symptoms (pyelonephritis, pneumonia) | 3 |
| `acute_complicated_injury`: acute complicated injury (fracture, head injury with loss of consciousness, injury with concern for tendon involvement) | 3 |
| `chronic_severe_exacerbation`: chronic illness with severe exacerbation | 4 |
| `threat_to_life_or_function`: acute or chronic illness or injury that poses a threat to life or bodily function | 4 |

**Judgement call (AMA wording):** fever, body aches or fatigue in a minor illness treated to relieve
symptoms do **not** make it `acute_systemic`. Otitis media with a fever is `acute_uncomplicated`.

## Element 2: amount and complexity of data reviewed and analysed

Category 1 items (each counts once):
- `review_external_note`: review of prior external notes, **per unique source**
- `review_test_result`: review of the result of a unique test **not ordered at this visit**
- `order_test`: ordering a unique test. **Ordering includes reviewing its result**, so a test ordered
  and reviewed at the same visit counts once.
- `independent_historian`: history obtained from someone else because the patient cannot give a
  complete or reliable one (a young child, a confused adult)

Category 2: `independent_interpretation`, the clinician's own interpretation of a test (image,
tracing) whose interpretation they do not bill separately, for example "my read" of an X-ray
while the radiologist's report is pending.

Category 3: `discussion_external`, discussion of management or test interpretation with an
external physician or appropriate source (on-call specialist, ED physician, poison control).

| Level | Requirement |
|---|---|
| Minimal (1) | Less than limited |
| Limited (2) | 2 Category 1 tests or documents, **or** an independent historian |
| Moderate (3) | 1 of 3 categories: Category 1 with 3 items (tests, documents, historian in any combination), **or** an independent interpretation, **or** a discussion |
| Extensive (4) | 2 of those 3 categories |

**Not counted:** a test whose interpretation is billed separately by the same clinician (for
example an ECG "tracing and interpretation billed separately"); return precautions.

## Element 3: risk of complications from patient management

| Type | Level |
|---|---|
| `minimal_risk`: rest, fluids, reassurance, cool compresses, superficial dressings, observation | 1 |
| `low_risk`: over-the-counter drugs, braces and splints for sprains, physical therapy | 2 |
| `prescription_drug_management`: prescribing, refilling, changing, or giving a prescription drug in clinic | 3 |
| `minor_surgery_with_risk_factors` | 3 |
| `sdoh_limits_care`: diagnosis or treatment significantly limited by social determinants of health | 3 |
| `drug_intensive_monitoring`: drug therapy requiring intensive monitoring for toxicity | 4 |
| `parenteral_controlled_substance` | 4 |
| `emergency_major_surgery` | 4 |
| `hospitalization_or_escalation`: decision regarding hospitalization or escalation, including sending a patient to the ED for admission or emergency evaluation | 4 |

Risk is the **highest** item. A decision is what counts, not a warning: "go to the ED if it gets
worse" is a return precaution, not a decision regarding hospitalization.

## Billed code and decision labels

Each note also carries the code the clinic billed. The correct decision follows from the label:
billed code equal to the supported code means **BILL**; anything else means **HOLD** (overcoded:
denial and audit risk; undercoded: revenue left behind).

## Known limits

- Labels were written with Claude Code against this guide. **No certified coder has reviewed them.**
- The notes are synthetic. No real patient data is used anywhere in this project.
- Payer-specific rules (for example urgent care S-codes, or a payer's own downcoding policy) are not modelled.
