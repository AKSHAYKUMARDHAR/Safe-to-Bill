"""Pipeline C: an LLM extracts MDM elements with quotes; code verifies them and computes the level.

The model never picks the code. Responses are cached on disk (keyed by model, prompt version, run
number and note), so evaluation reruns cost nothing and stay reproducible.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Callable, Literal

from pydantic import BaseModel

from .mdm import DATA_TYPES, PROBLEM_BASE, RISK_BASE, Element

ROOT = Path(__file__).resolve().parents[1]
PROMPT_VERSION = "v1"
PROMPT_FILE = ROOT / "prompts" / f"extract_{PROMPT_VERSION}.md"
CACHE_DIR = ROOT / "eval" / "cache"
TEMPERATURE = 1.0  # two runs must agree; at temperature 0 they would agree by construction


class Problem(BaseModel):
    type: Literal[tuple(PROBLEM_BASE)]  # type: ignore[valid-type]
    name: str
    quote: str


class DataItem(BaseModel):
    type: Literal[DATA_TYPES]  # type: ignore[valid-type]
    name: str
    quote: str


class RiskItem(BaseModel):
    type: Literal[tuple(RISK_BASE)]  # type: ignore[valid-type]
    name: str
    quote: str


class Extraction(BaseModel):
    problems: list[Problem]
    data: list[DataItem]
    risk: list[RiskItem]


class LLMError(RuntimeError):
    pass


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    return value.split("#", 1)[0].strip() if value else default


def to_elements(ex: Extraction) -> list[Element]:
    out = [Element("problem", p.type, p.name, p.quote) for p in ex.problems]
    out += [Element("data", d.type, d.name, d.quote) for d in ex.data]
    out += [Element("risk", r.type, r.name, r.quote) for r in ex.risk]
    return out


class LLMExtractor:
    def __init__(self, call_fn: Callable[[str], str] | None = None, model: str | None = None,
                 cache_dir: Path | None = CACHE_DIR, rpm: int | None = None, max_attempts: int = 4,
                 cache_only: bool = False):
        self.model = model or _env("GEMINI_MODEL", "gemini-3.1-flash-lite")
        self.cache_dir = cache_dir
        self.cache_only = cache_only  # re-scoring: never call the provider
        self.min_interval = 60.0 / (rpm or int(_env("GEMINI_RPM", "10") or 10))
        self.max_attempts = max_attempts
        self._last_call = 0.0
        self._call_fn = call_fn
        self._client = None
        self.prompt_template = PROMPT_FILE.read_text(encoding="utf-8")
        self.calls = 0
        self.cache_hits = 0

    # -- provider ------------------------------------------------------------
    def _gemini(self, prompt: str) -> str:
        from google import genai
        from google.genai import types

        if self._client is None:
            key = _env("GEMINI_API_KEY")
            if not key:
                raise LLMError("GEMINI_API_KEY is not set")
            self._client = genai.Client(api_key=key)
        resp = self._client.models.generate_content(
            model=self.model,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=TEMPERATURE,
                response_mime_type="application/json",
                response_schema=Extraction,
            ),
        )
        if not resp.text:
            raise LLMError("empty response")
        return resp.text

    def _call(self, prompt: str) -> str:
        if self._call_fn is not None:
            return self._call_fn(prompt)
        delay = 5.0
        for attempt in range(1, self.max_attempts + 1):
            wait = self.min_interval - (time.monotonic() - self._last_call)
            if wait > 0:
                time.sleep(wait)
            self._last_call = time.monotonic()
            try:
                self.calls += 1
                return self._gemini(prompt)
            except LLMError:
                raise
            except Exception as exc:  # provider errors: retry a capped number of times
                code = getattr(exc, "code", None)
                retryable = code in (429, 500, 502, 503, 504) or code is None
                if attempt == self.max_attempts or not retryable:
                    raise LLMError(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
                time.sleep(delay)
                delay *= 2
        raise LLMError("unreachable")

    # -- public ----------------------------------------------------------------
    def prompt(self, note: str, patient_type: str) -> str:
        return (self.prompt_template.replace("{{NOTE}}", note)
                .replace("{{PATIENT_TYPE}}", patient_type))

    def _cache_path(self, note: str, patient_type: str, run: int) -> Path | None:
        if self.cache_dir is None:
            return None
        key = f"{self.model}|{PROMPT_VERSION}|{TEMPERATURE}|{run}|{patient_type}|{note}"
        return self.cache_dir / f"{hashlib.sha256(key.encode('utf-8')).hexdigest()[:24]}.json"

    def extract(self, note: str, patient_type: str, run: int = 0) -> list[Element]:
        path = self._cache_path(note, patient_type, run)
        if path is not None and path.exists():
            self.cache_hits += 1
            raw = json.loads(path.read_text(encoding="utf-8"))["response"]
        elif self.cache_only:
            raise LLMError("no cached answer for this note (cache-only mode)")
        else:
            raw = self._call(self.prompt(note, patient_type))
            if path is not None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(json.dumps({"model": self.model, "prompt_version": PROMPT_VERSION,
                                            "temperature": TEMPERATURE, "run": run,
                                            "response": raw}, indent=1), encoding="utf-8")
        try:
            return to_elements(Extraction.model_validate_json(raw))
        except Exception as exc:
            raise LLMError(f"unparseable response: {exc}") from exc
