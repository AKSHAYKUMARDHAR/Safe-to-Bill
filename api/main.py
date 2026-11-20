"""FastAPI service.

    uvicorn api.main:app --reload
    POST /check  {"note": "...", "patient_type": "established", "billed_code": "99214"}

The event log stores a hash of the note, never its text (notes are PHI in real use).
"""
from __future__ import annotations

import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from safe_to_bill.check import PIPELINES, check
from safe_to_bill.llm_extractor import LLMExtractor

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
LOG = Path(os.environ.get("EVENT_LOG", ROOT / "logs" / "events.jsonl"))
DEFAULT_PIPELINE = "llm" if os.environ.get("GEMINI_API_KEY") else "rules"

app = FastAPI(title="Safe to Bill?", version="0.1.0",
              description="Checks whether an urgent care visit note supports the billed E/M level.")
_llm: LLMExtractor | None = None


class CheckRequest(BaseModel):
    note: str = Field(min_length=20, max_length=20000)
    patient_type: Literal["new", "established"]
    billed_code: str = Field(pattern=r"^\d{5}$")
    pipeline: Literal[PIPELINES] | None = None  # type: ignore[valid-type]


def _log(event: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    with LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "default_pipeline": DEFAULT_PIPELINE}


@app.post("/check")
def run_check(req: CheckRequest) -> dict:
    global _llm
    pipeline = req.pipeline or DEFAULT_PIPELINE
    if pipeline.startswith("llm") and _llm is None:
        _llm = LLMExtractor(cache_dir=None)
    try:
        out = check(req.note, req.patient_type, req.billed_code, pipeline, llm=_llm)
    except FileNotFoundError:
        raise HTTPException(503, "The ML model is not trained; run python -m safe_to_bill.ml_baseline")
    d = out["decision"]
    _log({"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
          "note_sha256": hashlib.sha256(req.note.encode("utf-8")).hexdigest(),
          "pipeline": pipeline, "billed": req.billed_code, "supported": d["supported_code"],
          "action": d["action"], "reason": d["reason"], "latency_ms": out["latency_ms"],
          "error": bool(out.get("error"))})
    return out


@app.get("/stats")
def stats() -> dict:
    if not LOG.exists():
        return {"checks": 0}
    events = [json.loads(line) for line in LOG.read_text(encoding="utf-8").splitlines() if line.strip()]
    n = len(events)
    return {"checks": n,
            "actions": dict(Counter(e["action"] for e in events)),
            "reasons": dict(Counter(e["reason"] for e in events)),
            "auto_bill_rate": round(sum(e["action"] == "BILL" for e in events) / n, 3) if n else 0,
            "errors": sum(e["error"] for e in events)}
