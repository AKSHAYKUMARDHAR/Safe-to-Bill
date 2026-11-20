"""AMA office/outpatient E/M level from medical decision making (MDM).

Pure functions, no I/O. The labelling guide (docs/LABELLING.md) is the same table in prose.
Levels are 1 = straightforward/minimal, 2 = low/limited, 3 = moderate, 4 = high/extensive.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field

LEVEL_NAMES = {1: "straightforward", 2: "low", 3: "moderate", 4: "high"}
CODES = {
    "new": {1: "99202", 2: "99203", 3: "99204", 4: "99205"},
    "established": {1: "99212", 2: "99213", 3: "99214", 4: "99215"},
}
CODE_TO_LEVEL = {code: (ptype, lvl) for ptype, m in CODES.items() for lvl, code in m.items()}

PROBLEM_BASE = {
    "self_limited_minor": 1,          # 2+ of these -> 2
    "acute_uncomplicated": 2,
    "stable_acute": 2,
    "stable_chronic": 2,              # 2+ of these -> 3
    "chronic_exacerbation": 3,
    "undiagnosed_uncertain": 3,
    "acute_systemic": 3,
    "acute_complicated_injury": 3,
    "chronic_severe_exacerbation": 4,
    "threat_to_life_or_function": 4,
}
DATA_TYPES = (
    "review_external_note",
    "review_test_result",
    "order_test",
    "independent_historian",
    "independent_interpretation",
    "discussion_external",
)
RISK_BASE = {
    "minimal_risk": 1,
    "low_risk": 2,
    "prescription_drug_management": 3,
    "minor_surgery_with_risk_factors": 3,
    "sdoh_limits_care": 3,
    "drug_intensive_monitoring": 4,
    "parenteral_controlled_substance": 4,
    "emergency_major_surgery": 4,
    "hospitalization_or_escalation": 4,
}


@dataclass(frozen=True)
class Element:
    """One problem, data item or risk item found in a note, with the words that support it."""

    kind: str  # "problem" | "data" | "risk"
    type: str
    name: str = ""  # problem, test, source or drug, used to count unique items
    quote: str = ""


@dataclass
class MDMResult:
    problems: int
    data: int
    risk: int
    level: int
    elements: list[Element] = field(default_factory=list)

    def code(self, patient_type: str) -> str:
        return CODES[patient_type][self.level]

    def as_dict(self) -> dict:
        return {
            "problems": LEVEL_NAMES[self.problems],
            "data": LEVEL_NAMES[self.data],
            "risk": LEVEL_NAMES[self.risk],
            "level": LEVEL_NAMES[self.level],
        }


def _norm(name: str) -> str:
    return " ".join(name.lower().replace("-", " ").split())


def problems_level(types: list[str]) -> int:
    if not types:
        return 1
    counts = Counter(types)
    level = max(PROBLEM_BASE[t] for t in types)
    if counts["stable_chronic"] >= 2:
        level = max(level, 3)
    if counts["self_limited_minor"] >= 2:
        level = max(level, 2)
    return level


def data_level(items: list[Element]) -> int:
    tests = {_norm(e.name) or f"test{i}" for i, e in enumerate(items)
             if e.type in ("order_test", "review_test_result")}
    sources = {_norm(e.name) or f"src{i}" for i, e in enumerate(items)
               if e.type == "review_external_note"}
    historian = any(e.type == "independent_historian" for e in items)
    interpretation = any(e.type == "independent_interpretation" for e in items)
    discussion = any(e.type == "discussion_external" for e in items)

    cat1_docs = len(tests) + len(sources)
    categories = int(cat1_docs + historian >= 3) + int(interpretation) + int(discussion)
    if categories >= 2:
        return 4
    if categories == 1:
        return 3
    if cat1_docs >= 2 or historian:
        return 2
    return 1


def risk_level(types: list[str]) -> int:
    return max((RISK_BASE[t] for t in types), default=1)


def mdm_level(problems: int, data: int, risk: int) -> int:
    """Highest level at which at least 2 of the 3 elements meet or exceed it."""
    for level in (4, 3, 2):
        if sum(e >= level for e in (problems, data, risk)) >= 2:
            return level
    return 1


def score(elements: list[Element]) -> MDMResult:
    p = problems_level([e.type for e in elements if e.kind == "problem"])
    d = data_level([e for e in elements if e.kind == "data"])
    r = risk_level([e.type for e in elements if e.kind == "risk"])
    return MDMResult(p, d, r, mdm_level(p, d, r), list(elements))
