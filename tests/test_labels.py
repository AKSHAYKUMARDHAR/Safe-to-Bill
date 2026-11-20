"""The answer key must agree with the engine's own arithmetic: element levels -> level -> code -> decision."""
import json
from pathlib import Path

import pytest

from safe_to_bill.mdm import CODES, LEVEL_NAMES, mdm_level

NAME_TO_LEVEL = {v: k for k, v in LEVEL_NAMES.items()}
DATA = Path(__file__).resolve().parents[1] / "data" / "handwritten"


def _records():
    for split in ("dev", "holdout", "holdout2"):
        for rec in json.loads((DATA / f"{split}.json").read_text(encoding="utf-8")):
            yield pytest.param(rec, id=rec["id"])


@pytest.mark.parametrize("rec", list(_records()))
def test_label_is_consistent(rec):
    lab = rec["label"]
    p, d, r = (NAME_TO_LEVEL[lab[k]] for k in ("problems", "data", "risk"))
    level = mdm_level(p, d, r)
    assert LEVEL_NAMES[level] == lab["level"]
    assert CODES[rec["patient_type"]][level] == lab["code"]
    expected = "BILL" if rec["billed_code"] == lab["code"] else "HOLD"
    assert rec["decision"] == expected
    assert '"' not in rec["note"]


def test_holdout_mix_matches_prd():
    recs = json.loads((DATA / "holdout.json").read_text(encoding="utf-8"))
    over = sum(int(r["billed_code"]) > int(r["label"]["code"]) for r in recs)
    under = sum(int(r["billed_code"]) < int(r["label"]["code"]) for r in recs)
    correct = sum(r["billed_code"] == r["label"]["code"] for r in recs)
    assert (len(recs), correct, over, under) == (36, 19, 12, 5)


def test_holdout2_mix_matches_release_plan():
    recs = json.loads((DATA / "holdout2.json").read_text(encoding="utf-8"))
    over = sum(int(r["billed_code"]) > int(r["label"]["code"]) for r in recs)
    under = sum(int(r["billed_code"]) < int(r["label"]["code"]) for r in recs)
    assert (len(recs), len(recs) - over - under, over, under) == (24, 12, 7, 5)
