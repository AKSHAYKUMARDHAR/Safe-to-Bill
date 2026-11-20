"""Seeded generator of synthetic urgent care notes with labels by construction.

Each note is assembled from parts whose MDM element types are known, and the label is computed by
the same engine the checker uses. The notes are deliberately easy (templated wording): they train
the ML baseline and act as regression data. The hand-written sets are the real test.

    python -m safe_to_bill.generator          # writes data/generated/{train,dev}.jsonl
"""
from __future__ import annotations

import json
import random
from pathlib import Path

from .mdm import CODES, Element, score

# (type, name, history sentence, assessment phrase)
PROBLEMS = [
    ("self_limited_minor", "insect bite", "an itchy bump after a bug bite yesterday", "insect bite, local reaction"),
    ("self_limited_minor", "abrasion", "a scrape on the forearm after a fall", "superficial abrasion"),
    ("self_limited_minor", "common cold", "a runny nose and sneezing for 3 days", "common cold"),
    ("self_limited_minor", "sunburn", "red, sore shoulders after a day at the beach", "mild sunburn"),
    ("self_limited_minor", "splinter", "a splinter in the thumb", "splinter, removed"),
    ("acute_uncomplicated", "pharyngitis", "a sore throat for 2 days without cough", "acute pharyngitis"),
    ("acute_uncomplicated", "ankle sprain", "ankle pain after twisting it on a step", "ankle sprain"),
    ("acute_uncomplicated", "cystitis", "burning with urination for 2 days, no fever", "uncomplicated cystitis"),
    ("acute_uncomplicated", "otitis media", "ear pain since last night", "acute otitis media"),
    ("acute_uncomplicated", "conjunctivitis", "a red eye with discharge", "acute conjunctivitis"),
    ("acute_uncomplicated", "sinusitis", "facial pressure and congestion for 10 days", "acute sinusitis"),
    ("stable_acute", "cellulitis follow-up", "a recheck of cellulitis on day 4 of antibiotics", "cellulitis, improving"),
    ("stable_chronic", "hypertension", "a blood pressure medication refill", "hypertension, stable"),
    ("stable_chronic", "hypothyroidism", "a thyroid medication refill", "hypothyroidism, stable on treatment"),
    ("stable_chronic", "diabetes", "a diabetes medication refill", "type 2 diabetes, at goal"),
    ("chronic_exacerbation", "asthma", "wheezing for 2 days after a cold, known asthma", "asthma exacerbation"),
    ("chronic_exacerbation", "copd", "more shortness of breath and sputum, known COPD", "COPD exacerbation"),
    ("chronic_exacerbation", "gout", "a hot swollen big toe, known gout", "gout flare"),
    ("undiagnosed_uncertain", "mass", "a new lump in the neck for 3 weeks", "neck mass, undiagnosed, uncertain prognosis"),
    ("acute_systemic", "pneumonia", "fever, chills and productive cough for 4 days", "community-acquired pneumonia"),
    ("acute_systemic", "pyelonephritis", "fever and flank pain with urinary burning", "acute pyelonephritis"),
    ("acute_complicated_injury", "fracture", "wrist pain and deformity after a fall", "distal radius fracture"),
    ("acute_complicated_injury", "head injury", "a head injury with brief loss of consciousness", "concussion with loss of consciousness"),
    ("chronic_severe_exacerbation", "severe asthma", "a severe asthma attack not relieved by repeated inhaler use", "severe asthma exacerbation"),
    ("threat_to_life_or_function", "chest pain", "crushing chest pain with sweating", "suspected acute coronary syndrome"),
    ("threat_to_life_or_function", "stroke", "sudden arm weakness and slurred speech", "suspected acute stroke"),
    ("threat_to_life_or_function", "anaphylaxis", "lip swelling and wheezing after eating peanuts", "anaphylaxis"),
]

TESTS = ["rapid strep", "urinalysis", "urine culture", "pregnancy test", "rapid influenza test",
         "COVID-19 test", "chest X-ray", "CBC", "fingerstick glucose"]
TEST_SENTENCES = ["{t} ordered: {r}.", "{t} was ordered and came back {r}.", "Ordered a {t}, result {r}."]
SOURCES = ["ED discharge summary from last week", "cardiology clinic note", "PCP visit note from March"]
RELATIVES = ["mother", "father", "daughter", "caregiver"]

RISK = {
    "minimal_risk": ["Rest and fluids.", "Reassurance and cool compresses.", "Cleaned and covered with a bandage."],
    "low_risk": ["Ibuprofen OTC as needed.", "Acetaminophen OTC and rest.", "Brace and ibuprofen OTC."],
    "prescription_drug_management": ["Amoxicillin prescribed for 10 days.", "Prednisone 40 mg for 5 days prescribed.",
                                     "Refilled the usual medication for 90 days.", "Cephalexin 500 mg prescribed."],
    "sdoh_limits_care": ["Patient cannot afford the preferred antibiotic and has no transportation for follow-up, so the plan was changed to a cheaper option given today."],
    "hospitalization_or_escalation": ["EMS called for transfer to the ED for admission.",
                                      "Sent to the emergency department for evaluation and possible admission."],
}
RISK_BY_PROBLEM_LEVEL = {
    1: {"minimal_risk": 5, "low_risk": 4, "prescription_drug_management": 1},
    2: {"minimal_risk": 2, "low_risk": 4, "prescription_drug_management": 4},
    3: {"low_risk": 2, "prescription_drug_management": 7, "sdoh_limits_care": 1, "hospitalization_or_escalation": 1},
    4: {"prescription_drug_management": 1, "hospitalization_or_escalation": 9},
}


def _pick_weighted(rng: random.Random, weights: dict[str, int]) -> str:
    keys = list(weights)
    return rng.choices(keys, weights=[weights[k] for k in keys])[0]


def make_note(rng: random.Random, idx: int) -> dict:
    from .mdm import PROBLEM_BASE

    patient_type = rng.choice(["new", "established"])
    n_problems = 2 if rng.random() < 0.25 else 1
    problems = rng.sample(PROBLEMS, n_problems)
    elements: list[Element] = []
    age = rng.randint(4, 80)
    sex = rng.choice(["M", "F"])
    history = " and ".join(p[2] for p in problems)
    lines = [f"{age}{sex} with {history}."]

    if age < 7 and rng.random() < 0.8:
        rel = rng.choice(RELATIVES[:2])
        sent = f"History obtained from {rel}; the patient is too young to give a reliable history."
        lines.append(sent)
        elements.append(Element("data", "independent_historian", rel, sent))

    for t in rng.sample(TESTS, rng.choice([0, 0, 1, 1, 2, 3])):
        sent = rng.choice(TEST_SENTENCES).format(t=t, r=rng.choice(["negative", "normal", "positive"]))
        sent = sent[0].upper() + sent[1:]
        lines.append(sent)
        elements.append(Element("data", "order_test", t, sent))
        if t == "chest X-ray" and rng.random() < 0.5:
            s2 = "My read of the film: no pneumothorax; radiology over-read pending."
            lines.append(s2)
            elements.append(Element("data", "independent_interpretation", t, s2))
    if rng.random() < 0.15:
        src = rng.choice(SOURCES)
        sent = f"Reviewed the {src}."
        lines.append(sent)
        elements.append(Element("data", "review_external_note", src, sent))
    if rng.random() < 0.1:
        sent = "Discussed the case with the on-call specialist, Dr. Rao."
        lines.append(sent)
        elements.append(Element("data", "discussion_external", "on-call specialist", sent))

    assessment = "; ".join(p[3] for p in problems)
    lines.append(f"Assessment: {assessment}.")
    for p in problems:
        elements.append(Element("problem", p[0], p[1], p[3]))

    top = max(PROBLEM_BASE[p[0]] for p in problems)
    rtype = _pick_weighted(rng, RISK_BY_PROBLEM_LEVEL[top])
    rtext = rng.choice(RISK[rtype])
    lines.append(f"Plan: {rtext}")
    elements.append(Element("risk", rtype, rtype, rtext))

    result = score(elements)
    supported = CODES[patient_type][result.level]
    roll = rng.random()
    billed_level = result.level
    if roll < 0.30 and result.level < 4:
        billed_level += 1
    elif roll < 0.45 and result.level > 1:
        billed_level -= 1
    billed = CODES[patient_type][billed_level]
    return {
        "id": f"G{idx:04d}",
        "patient_type": patient_type,
        "billed_code": billed,
        "note": "\n".join(lines),
        "label": {**result.as_dict(), "code": supported},
        "decision": "BILL" if billed == supported else "HOLD",
    }


def generate(n: int = 1000, seed: int = 7) -> list[dict]:
    rng = random.Random(seed)
    return [make_note(rng, i) for i in range(n)]


def main() -> None:
    out = Path(__file__).resolve().parents[1] / "data" / "generated"
    out.mkdir(parents=True, exist_ok=True)
    notes = generate()
    splits = {"train": notes[:800], "dev": notes[800:]}
    for name, rows in splits.items():
        with (out / f"{name}.jsonl").open("w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        print(f"{name}: {len(rows)} notes")


if __name__ == "__main__":
    main()
