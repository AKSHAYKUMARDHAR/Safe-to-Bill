"""BILL or HOLD: the only place a claim decision is made."""
from __future__ import annotations

from dataclasses import asdict, dataclass

from .mdm import CODE_TO_LEVEL, CODES


@dataclass
class Decision:
    action: str  # "BILL" | "HOLD"
    reason: str  # "match" | "overcoded" | "undercoded" | "not_confident" | "wrong_family" | "unsupported_code"
    message: str
    billed_code: str
    supported_code: str | None

    def as_dict(self) -> dict:
        return asdict(self)


def decide(billed_code: str, patient_type: str, supported_level: int | None,
           confident: bool, why_not_confident: str = "") -> Decision:
    supported = CODES[patient_type][supported_level] if supported_level else None
    if billed_code not in CODE_TO_LEVEL:
        return Decision("HOLD", "unsupported_code",
                        f"{billed_code} is not an office/outpatient E/M code this check covers.",
                        billed_code, supported)
    family, billed_level = CODE_TO_LEVEL[billed_code]
    if family != patient_type:
        return Decision("HOLD", "wrong_family",
                        f"{billed_code} is a {family}-patient code but the patient is {patient_type}.",
                        billed_code, supported)
    if not confident or supported_level is None:
        return Decision("HOLD", "not_confident",
                        f"Needs a coder: {why_not_confident or 'the check is not confident'}.",
                        billed_code, supported)
    if billed_level == supported_level:
        return Decision("BILL", "match", f"The note supports {billed_code}.", billed_code, supported)
    if billed_level > supported_level:
        return Decision("HOLD", "overcoded",
                        f"Billed {billed_code}, but the note supports {supported}: denial, downcode and audit risk.",
                        billed_code, supported)
    return Decision("HOLD", "undercoded",
                    f"Billed {billed_code}, but the note supports {supported}: revenue left behind.",
                    billed_code, supported)
