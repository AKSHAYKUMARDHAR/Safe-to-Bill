"""One entry point for all pipelines: note in, BILL/HOLD decision and evidence out."""
from __future__ import annotations

import time

from . import rules_extractor
from .decide import decide
from .llm_extractor import LLMError, LLMExtractor
from .mdm import LEVEL_NAMES, MDMResult, score
from .ml_baseline import MLBaseline
from .verify import verify

PIPELINES = ("rules", "ml", "llm", "llm1")


def _evidence(result: MDMResult) -> list[dict]:
    return [{"kind": e.kind, "type": e.type, "name": e.name, "quote": e.quote} for e in result.elements]


def check(note: str, patient_type: str, billed_code: str, pipeline: str = "llm", *,
          llm: LLMExtractor | None = None, ml: MLBaseline | None = None) -> dict:
    if pipeline not in PIPELINES:
        raise ValueError(f"pipeline must be one of {PIPELINES}")
    if patient_type not in ("new", "established"):
        raise ValueError("patient_type must be 'new' or 'established'")
    t0 = time.perf_counter()
    out: dict = {"pipeline": pipeline, "elements": [], "dropped_quotes": 0, "run_levels": []}
    level, confident, why = None, False, ""

    if pipeline == "rules":
        kept, dropped = verify(rules_extractor.extract(note), note)
        result = score(kept)
        level, out["dropped_quotes"] = result.level, len(dropped)
        out.update(elements=_evidence(result), mdm=result.as_dict(), run_levels=[result.level])
        confident = any(e.kind == "problem" for e in kept)
        why = "no problem found in the note"

    elif pipeline == "ml":
        ml = ml or MLBaseline.load()
        level, prob = ml.predict(note)
        out.update(probability=round(prob, 3), threshold=ml.threshold, run_levels=[level])
        confident = prob >= ml.threshold
        why = f"model probability {prob:.2f} is below the {ml.threshold:.2f} gate"

    else:
        llm = llm or LLMExtractor()
        runs = 2 if pipeline == "llm" else 1
        results: list[MDMResult] = []
        try:
            for r in range(runs):
                kept, dropped = verify(llm.extract(note, patient_type, run=r), note)
                out["dropped_quotes"] += len(dropped)
                results.append(score(kept))
        except LLMError as exc:
            out["error"] = str(exc)
            why = "the model was unavailable"
        if results:
            out.update(elements=_evidence(results[0]), mdm=results[0].as_dict(),
                       run_levels=[r.level for r in results])
        if results and len(results) == runs:
            levels = {r.level for r in results}
            has_problem = any(e.kind == "problem" for e in results[0].elements)
            if len(levels) > 1:
                why = "two readings of the note disagree (" + " vs ".join(
                    LEVEL_NAMES[r.level] for r in results) + ")"
            elif not has_problem:
                why = "no verified problem in the note"
            else:
                level, confident = results[0].level, True

    decision = decide(billed_code, patient_type, level if confident else
                      (out["run_levels"][0] if out["run_levels"] else None), confident, why)
    out["decision"] = decision.as_dict()
    out["supported_level"] = LEVEL_NAMES.get(level) if level else None
    out["latency_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out
