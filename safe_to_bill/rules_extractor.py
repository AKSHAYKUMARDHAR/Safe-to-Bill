"""Pipeline A: keyword and pattern extraction of MDM elements (the deterministic baseline).

Deliberately simple and general: clinical cue words, a negation check, and a skip for return
precautions. It quotes the clause it matched, so its quotes are always in the note.
"""
from __future__ import annotations

import re

from .mdm import PROBLEM_BASE, Element

_NEG = re.compile(r"\b(no|not|without|negative for|denies|rules? out)\s+(\w+\s+){0,2}$", re.I)
_PRECAUTION = re.compile(r"\bif\b|precaution|return to|\brtc\b|watch for", re.I)
_ASSESS = re.compile(r"^\s*(assessment|a/p|a:|impression|dx|diagnosis)\b", re.I)

PROBLEM_RULES: list[tuple[str, str]] = [
    ("threat_to_life_or_function",
     r"\b(stemi|acute coronary|stroke|anaphylaxis|appendicitis|respiratory failure|suicidal|sepsis|"
     r"pulmonary embol\w*|hypotension|threat to (life|bodily function))\b"),
    ("chronic_severe_exacerbation",
     r"\bsevere \w* ?exacerbation\b|status asthmaticus|not responding to (treatment|nebulizer)"),
    ("chronic_exacerbation",
     r"\b(asthma|copd|migraines?|gout|eczema|gerd|diabetes|hypertension|heart failure)\b[^.;]*?"
     r"\b(exacerbation|flare|worsening|worse|uncontrolled|progression|poorly controlled|not responding)\b"),
    ("chronic_exacerbation", r"\b(exacerbation|flare)\b[^.;]*?\b(asthma|copd|gout|eczema)\b"),
    ("undiagnosed_uncertain",
     r"\b(uncertain prognosis|undiagnosed|unclear (cause|etiology)|mass|lump|jaundice|unexplained)\b"),
    ("acute_systemic", r"\b(pyelonephritis|pneumonia|systemic symptoms)\b"),
    ("acute_complicated_injury",
     r"\b(fracture|loss of consciousness|concussion|dislocation|tendon|deformity|complicated injury)\b"),
    ("stable_chronic",
     r"\b(hypertension|diabetes|hypothyroidism|asthma|depression|hyperlipidemia|copd|gout)\b[^.;]*?"
     r"\b(stable|well controlled|controlled|at goal)\b"),
    ("stable_acute", r"\b(improving|resolving)\b"),
    ("self_limited_minor",
     r"\b(insect bite|bug bite|tick bite|abrasion|sunburn|common cold|viral uri|splinter|skin tag|"
     r"blister|paper cut|first-degree burn|superficial|resolved)\b"),
    ("acute_uncomplicated",
     r"\b(pharyngitis|sprain|strain|otitis|conjunctivitis|cystitis|uti|gastroenteritis|sinusitis|"
     r"bronchitis|cellulitis|cough|dermatitis|rash)\b"),
]

TESTS: dict[str, str] = {
    "rapid strep": r"rapid strep|strep test",
    "influenza test": r"\binfluenza\b|\bflu (a|b|test)\b|rapid flu",
    "covid test": r"\bcovid",
    "urinalysis": r"urinalysis|\bua\b|urine dip",
    "urine culture": r"urine culture",
    "pregnancy test": r"pregnancy test|\bhcg\b",
    "chest x-ray": r"chest x-?ray|\bcxr\b",
    "x-ray": r"(?<!chest )\bx-?ray\b|radiograph",
    "ct": r"\bct\b",
    "ultrasound": r"ultrasound",
    "mammogram": r"mammogram",
    "ecg": r"\b(ecg|ekg)\b",
    "cbc": r"\bcbc\b",
    "cmp": r"\bcmp\b|metabolic panel",
    "glucose": r"fingerstick|\bglucose\b",
    "liver tests": r"liver (test|function)|\blfts?\b",
    "tsh": r"\btsh\b",
    "a1c": r"\ba1c\b",
}
_TEST_ACTION = re.compile(r"ordered|sent|performed|obtained|reviewed|result|negative|positive|:", re.I)
_EXTERNAL = re.compile(
    r"reviewed (his|her|their|the)?\s*((?:\w+\s){0,4}?)(note|notes|records|discharge summary|summary)\b", re.I)
_HISTORIAN = re.compile(
    r"history (obtained |provided |given )?(from|by) (his |her |the )?(mother|father|parent|mom|dad|wife|"
    r"husband|caregiver|daughter|son|family)|\bper (his |her )?(mother|father|parent|wife)\b", re.I)
_INTERP = re.compile(r"\bmy (read|interpretation)\b|independently interpreted|personally (reviewed|read) the "
                     r"(images|films|tracing)", re.I)
_DISCUSS = re.compile(r"\bdiscussed (with|the case with)\b", re.I)
_BILLED_SEPARATELY = re.compile(r"billed separately", re.I)

RISK_RULES: list[tuple[str, str]] = [
    ("hospitalization_or_escalation",
     r"transfer(red)? to the (ed|emergency)|transfer to the (ed|emergency)|sent to the (ed|emergency)|"
     r"\bems called|called ems|ambulance|for admission|\badmit|stroke alert|emergency transfer"),
    ("parenteral_controlled_substance", r"\b(morphine|hydromorphone|fentanyl|ketamine|dilaudid)\b"),
    ("sdoh_limits_care", r"cannot afford|can't afford|no transportation|homeless|uninsured"),
    ("prescription_drug_management",
     r"prescribed|prescription|\brx\b|refill|\bstarted (on )?[a-z]+ \d+(\.\d+)?\s?(mg|mcg|units)\b|"
     r"\bincreased \w+ to \d|\bcontinue \w+ \d+\s?mg|"
     r"given in clinic|\bim given|mg im\b|nebulizer"),
    ("low_risk", r"\botc\b|over-the-counter|ibuprofen|acetaminophen|\bbrace\b|physical therapy|"
                 r"dextromethorphan|hydrocortisone|\baloe\b"),
    ("minimal_risk", r"\brest\b|fluids|reassurance|cool compress|bandage|dressing|observe|\bice\b|"
                     r"elevat|gargle|honey|keep clean|rehydration"),
]


def _clauses(text: str) -> list[str]:
    parts = re.split(r"(?<=[.;])\s+|\n|\s(?=\d\)\s)", text)
    return [p.strip() for p in parts if p and p.strip()]


def _negated(clause: str, start: int) -> bool:
    return bool(_NEG.search(clause[:start]))


def _assessment_text(note: str) -> str:
    lines = note.splitlines()
    for i, line in enumerate(lines):
        if _ASSESS.match(line):
            return "\n".join(lines[i:])
    return note


def extract(note: str) -> list[Element]:
    elements: list[Element] = []

    # Problems: from the assessment section; one problem (the highest) per clause.
    seen_problems: set[tuple[str, str]] = set()
    for clause in _clauses(_assessment_text(note)):
        if _PRECAUTION.search(clause):
            continue
        best: tuple[int, str, str] | None = None
        for ptype, pattern in PROBLEM_RULES:
            for m in re.finditer(pattern, clause, re.I):
                if _negated(clause, m.start()):
                    continue
                cand = (PROBLEM_BASE[ptype], ptype, m.group(0).lower())
                if best is None or cand[0] > best[0]:
                    best = cand
        if best:
            key = (best[1], best[2])
            if key not in seen_problems:
                seen_problems.add(key)
                elements.append(Element("problem", best[1], best[2], clause))
        # A second stable chronic illness in the same clause ("hypertension and diabetes, stable")
        diseases = re.findall(r"\b(hypertension|diabetes|hypothyroidism|depression|hyperlipidemia)\b", clause, re.I)
        if best and best[1] == "stable_chronic" and len({d.lower() for d in diseases}) > 1:
            for d in {d.lower() for d in diseases} - {best[2]}:
                if ("stable_chronic", d) not in seen_problems:
                    seen_problems.add(("stable_chronic", d))
                    elements.append(Element("problem", "stable_chronic", d, clause))

    # Data: anywhere in the note.
    tests_seen: set[str] = set()
    for clause in _clauses(note):
        if _BILLED_SEPARATELY.search(clause):
            continue
        if _TEST_ACTION.search(clause):
            for name, pattern in TESTS.items():
                for m in re.finditer(pattern, clause, re.I):
                    if _negated(clause, m.start()) or name in tests_seen:
                        continue
                    tests_seen.add(name)
                    elements.append(Element("data", "order_test", name, clause))
        m = _EXTERNAL.search(clause)
        if m:
            elements.append(Element("data", "review_external_note", m.group(0).lower(), clause))
        if _HISTORIAN.search(clause):
            elements.append(Element("data", "independent_historian", "historian", clause))
        if _INTERP.search(clause):
            elements.append(Element("data", "independent_interpretation", "interpretation", clause))
        if _DISCUSS.search(clause):
            elements.append(Element("data", "discussion_external", "discussion", clause))

    # Risk: anywhere, per comma-separated plan item, skipping return precautions.
    for clause in _clauses(note):
        for part in re.split(r",\s+|\s+and\s+", clause):
            if not part or _PRECAUTION.search(part):
                continue
            for rtype, pattern in RISK_RULES:
                m = re.search(pattern, part, re.I)
                if m and not _negated(part, m.start()):
                    elements.append(Element("risk", rtype, m.group(0).lower(), part))
                    break
    return elements
