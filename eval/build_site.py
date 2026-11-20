"""Build the static results explorer (docs/index.html) from cached model answers and run logs.

    python -m eval.build_site

Cache only: it never calls the model. Release run 1 is shown with the verifier it ran with (v1);
release run 2 with v2. Every decision shown is the one the logged release run made.
"""
from __future__ import annotations

import glob
import html
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from safe_to_bill.check import check  # noqa: E402
from safe_to_bill.llm_extractor import LLMExtractor  # noqa: E402
from safe_to_bill.mdm import LEVEL_NAMES, RISK_BASE, PROBLEM_BASE  # noqa: E402

RELEASES = [
    {"key": "run2", "split": "holdout2", "verifier": "v2", "title": "Release run 2",
     "sub": "24 fresh notes, frozen and pushed before the run"},
    {"key": "run1", "split": "holdout", "verifier": "v1", "title": "Release run 1",
     "sub": "36 held-out notes, run once"},
]
TYPE_LABEL = {
    "self_limited_minor": "minor problem", "acute_uncomplicated": "acute, uncomplicated",
    "stable_acute": "stable acute illness", "stable_chronic": "stable chronic illness",
    "chronic_exacerbation": "chronic illness, exacerbation", "undiagnosed_uncertain": "undiagnosed, uncertain prognosis",
    "acute_systemic": "acute illness, systemic symptoms", "acute_complicated_injury": "acute complicated injury",
    "chronic_severe_exacerbation": "chronic illness, severe exacerbation",
    "threat_to_life_or_function": "threat to life or bodily function",
    "order_test": "test ordered", "review_test_result": "outside result reviewed",
    "review_external_note": "external records reviewed", "independent_historian": "independent historian",
    "independent_interpretation": "own interpretation", "discussion_external": "discussion with external physician",
    "minimal_risk": "minimal risk", "low_risk": "low risk (OTC, brace)",
    "prescription_drug_management": "prescription drug management", "minor_surgery_with_risk_factors": "minor surgery, risk factors",
    "sdoh_limits_care": "limited by social determinants", "drug_intensive_monitoring": "drug needing intensive monitoring",
    "parenteral_controlled_substance": "parenteral controlled substance", "emergency_major_surgery": "emergency major surgery",
    "hospitalization_or_escalation": "decision to hospitalise / escalate",
}


def _spans(note: str, quotes: list[str]) -> list[tuple[int, int]]:
    spans = []
    for q in quotes:
        for piece in re.split(r"\.\.\.|…|(?<=[.;!?])\s+", q):
            words = re.findall(r"\S+", piece.strip().strip(".;:,"))
            if not words:
                continue
            m = re.search(r"\s+".join(re.escape(w) for w in words), note, re.I)
            if m:
                spans.append((m.start(), m.end()))
    spans.sort()
    merged: list[list[int]] = []
    for s, e in spans:
        if merged and s <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], e)
        else:
            merged.append([s, e])
    return [(s, e) for s, e in merged]


def _note_html(note: str, quotes: list[str]) -> str:
    out, pos = [], 0
    for s, e in _spans(note, quotes):
        out.append(html.escape(note[pos:s]))
        out.append(f"<mark>{html.escape(note[s:e])}</mark>")
        pos = e
    out.append(html.escape(note[pos:]))
    return "".join(out)


def _release_data(rel: dict, llm: LLMExtractor) -> dict:
    notes = json.loads((ROOT / "data" / "handwritten" / f"{rel['split']}.json").read_text(encoding="utf-8"))
    logs = sorted(glob.glob(str(ROOT / "eval" / "runs" / f"*_{rel['split']}_release.json")))
    if not logs:
        raise SystemExit(f"no release log for {rel['split']}")
    log = json.loads(Path(logs[-1]).read_text(encoding="utf-8"))
    rows = []
    for n in notes:
        res = check(n["note"], n["patient_type"], n["billed_code"], "llm", llm=llm,
                    verifier=rel["verifier"])
        d = res["decision"]
        elements = [{"kind": e["kind"], "type": TYPE_LABEL.get(e["type"], e["type"]),
                     "level": LEVEL_NAMES[(PROBLEM_BASE | RISK_BASE).get(e["type"], 0)] if e["kind"] != "data" else "",
                     "quote": e["quote"]} for e in res["elements"]]
        rows.append({
            "id": n["id"], "patient_type": n["patient_type"], "billed": n["billed_code"],
            "key_code": n["label"]["code"], "key": n["label"], "key_note": n["label_note"],
            "action": d["action"], "reason": d["reason"], "message": d["message"],
            "supported": d["supported_code"], "mdm": res.get("mdm", {}),
            "runs": [LEVEL_NAMES[x] for x in res["run_levels"]],
            "elements": elements, "note_html": _note_html(n["note"], [e["quote"] for e in res["elements"]]),
            "decision_right": d["action"] == n["decision"],
        })
    return {"key": rel["key"], "title": rel["title"], "sub": rel["sub"], "timestamp": log["timestamp"],
            "model": log["config"]["model"], "verifier": rel["verifier"], "metrics": log["pipelines"], "rows": rows}


def main() -> None:
    llm = LLMExtractor(cache_only=True)
    data = [_release_data(r, llm) for r in RELEASES]
    template = (ROOT / "eval" / "site_template.html").read_text(encoding="utf-8")
    page = template.replace("/*DATA*/null", json.dumps(data))
    out = ROOT / "docs" / "index.html"
    out.write_text(page, encoding="utf-8")
    (ROOT / "docs" / ".nojekyll").write_text("", encoding="utf-8")
    print(f"wrote {out.relative_to(ROOT)} ({len(page) // 1024} KB), {llm.calls} model calls, {llm.cache_hits} cache hits")


if __name__ == "__main__":
    main()
