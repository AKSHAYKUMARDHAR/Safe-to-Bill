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


def quote_in_note(quote: str, note: str) -> bool:
    """True when the quote is in the note.

    A quote may join pieces of the note: on an ellipsis, or (since release run 1) whole sentences
    stitched together with the text between them left out. Every piece must appear in the note,
    in order; a stitched sentence must have at least 3 words, so a stray "No." cannot pass.
    """
    hay = normalize(note)
    parts = [p for p in (normalize(x) for x in _ELLIPSIS.split(quote)) if p]
    if not parts:
        return False
    if _in_order(parts, hay):
        return True
    pieces = []
    for part in parts:
        for sentence in _SENTENCE_END.split(part):
            s = normalize(sentence)
            if s:
                pieces.append(s)
    if len(pieces) < 2 or any(len(p.split()) < MIN_FRAGMENT_WORDS for p in pieces):
        return False
    return _in_order(pieces, hay)


def verify(elements: list[Element], note: str) -> tuple[list[Element], list[Element]]:
    kept, dropped = [], []
    for e in elements:
        (kept if quote_in_note(e.quote, note) else dropped).append(e)
    return kept, dropped
