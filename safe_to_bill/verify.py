"""Quote checks: an element is kept only if the words it cites are in the note."""
from __future__ import annotations

import re
import unicodedata

from .mdm import Element

_ELLIPSIS = re.compile(r"\.\.\.|…")


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).lower()
    text = (text.replace("’", "'").replace("‘", "'")
                .replace("–", "-").replace("—", "-"))
    text = re.sub(r"\s+", " ", text)
    return text.strip(" .;:,\"'")


_SENTENCE_END = re.compile(r"(?<=[.;!?])\s+")
MIN_FRAGMENT_WORDS = 3


def _in_order(parts: list[str], hay: str) -> bool:
    pos = 0
    for part in parts:
        found = hay.find(part, pos)
        if found < 0:
            return False
        pos = found + len(part)
    return True


def quote_in_note(quote: str, note: str, allow_stitched: bool = True) -> bool:
    """True when the quote is in the note.

    A quote may join pieces of the note: on an ellipsis, or (verifier v2, after release run 1)
    whole sentences stitched together with the text between them left out. Every piece must
    appear in the note, in order; a stitched sentence must have at least 3 words, so a stray "No."
    cannot pass. allow_stitched=False is verifier v1, kept to reproduce release run 1 exactly.
    """
    hay = normalize(note)
    parts = [p for p in (normalize(x) for x in _ELLIPSIS.split(quote)) if p]
    if not parts:
        return False
    if _in_order(parts, hay):
        return True
    if not allow_stitched:
        return False
    pieces = []
    for part in parts:
        for sentence in _SENTENCE_END.split(part):
            s = normalize(sentence)
            if s:
                pieces.append(s)
    if len(pieces) < 2 or any(len(p.split()) < MIN_FRAGMENT_WORDS for p in pieces):
        return False
    return _in_order(pieces, hay)


# Verifier v3 (after release run 2): a problem only counts if it was addressed at this visit.
# A quote from a past-history or problem-list line, or one that says "not addressed", is copied
# history (the copy-forward pattern payer audits look for), not a problem addressed today.
_UNADDRESSED = re.compile(r"^(pmh|past medical history|problem list)\b|\bnot addressed\b|carried forward", re.I)
VERIFIERS = ("v1", "v2", "v3")


def addressed_today(e: Element) -> bool:
    return e.kind != "problem" or not _UNADDRESSED.search(normalize(e.quote))


def verify(elements: list[Element], note: str, verifier: str = "v3") -> tuple[list[Element], list[Element]]:
    """v1: exact quotes only (release run 1). v2: + stitched sentences (release run 2).
    v3: + drop problems quoted from past history or marked not addressed."""
    if verifier not in VERIFIERS:
        raise ValueError(f"verifier must be one of {VERIFIERS}")
    kept, dropped = [], []
    for e in elements:
        ok = quote_in_note(e.quote, note, allow_stitched=verifier != "v1")
        if ok and verifier == "v3":
            ok = addressed_today(e)
        (kept if ok else dropped).append(e)
    return kept, dropped
