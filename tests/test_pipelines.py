import json

from safe_to_bill import rules_extractor
from safe_to_bill.check import check
from safe_to_bill.generator import generate
from safe_to_bill.llm_extractor import LLMError, LLMExtractor
from safe_to_bill.mdm import LEVEL_NAMES, score

NOTE = ("26F with dysuria for 2 days. Urinalysis ordered: positive nitrites. Urine culture sent.\n"
        "Assessment: acute uncomplicated cystitis.\n"
        "Plan: nitrofurantoin prescribed; go to the ED if fever develops.")


def test_rules_find_elements_and_skip_precautions():
    r = score(rules_extractor.extract(NOTE))
    assert (r.problems, r.data, r.risk, r.level) == (2, 2, 3, 2)  # the ED line is a precaution


def test_rules_respect_negation():
    note = "Ottawa rules negative, so no X-ray.\nAssessment: ankle sprain.\nPlan: brace, ibuprofen OTC."
    assert not [e for e in rules_extractor.extract(note) if e.kind == "data"]


def test_generator_is_seeded_and_labels_match_the_engine():
    a, b = generate(50, seed=3), generate(50, seed=3)
    assert a == b
    assert {r["decision"] for r in a} == {"BILL", "HOLD"}
    for r in a:
        assert (r["billed_code"] == r["label"]["code"]) == (r["decision"] == "BILL")


def _fake(responses):
    calls = iter(responses)
    return lambda prompt: json.dumps(next(calls))


GOOD = {"problems": [{"type": "acute_uncomplicated", "name": "cystitis", "quote": "acute uncomplicated cystitis"}],
        "data": [{"type": "order_test", "name": "urinalysis", "quote": "Urinalysis ordered: positive nitrites"},
                 {"type": "order_test", "name": "urine culture", "quote": "Urine culture sent"}],
        "risk": [{"type": "prescription_drug_management", "name": "nitrofurantoin", "quote": "nitrofurantoin prescribed"}]}


def test_llm_two_agreeing_runs_bill():
    llm = LLMExtractor(call_fn=_fake([GOOD, GOOD]), cache_dir=None)
    out = check(NOTE, "established", "99213", "llm", llm=llm)
    assert out["decision"]["action"] == "BILL" and out["run_levels"] == [2, 2]


def test_llm_invented_quote_is_dropped_and_changes_nothing():
    lie = json.loads(json.dumps(GOOD))
    lie["risk"].append({"type": "hospitalization_or_escalation", "name": "ED", "quote": "admitted to hospital"})
    llm = LLMExtractor(call_fn=_fake([lie, GOOD]), cache_dir=None)
    out = check(NOTE, "established", "99213", "llm", llm=llm)
    assert out["dropped_quotes"] == 1 and out["decision"]["action"] == "BILL"


def test_llm_disagreement_holds():
    moderate = json.loads(json.dumps(GOOD))
    moderate["problems"][0]["type"] = "acute_systemic"
    llm = LLMExtractor(call_fn=_fake([GOOD, moderate]), cache_dir=None)
    out = check(NOTE, "established", "99213", "llm", llm=llm)
    assert out["decision"]["reason"] == "not_confident" and "disagree" in out["decision"]["message"]


def test_llm_failure_holds():
    def boom(prompt):
        raise LLMError("quota")
    out = check(NOTE, "established", "99213", "llm", llm=LLMExtractor(call_fn=boom, cache_dir=None))
    assert out["decision"]["action"] == "HOLD" and out["error"]


def test_cache_only_never_calls_the_provider(tmp_path):
    def must_not_call(prompt):
        raise AssertionError("provider called in cache-only mode")
    llm = LLMExtractor(call_fn=must_not_call, cache_dir=tmp_path, cache_only=True)
    out = check(NOTE, "established", "99213", "llm", llm=llm)
    assert out["decision"]["action"] == "HOLD" and "cache-only" in out["error"]


def test_prompt_keeps_note_as_data():
    p = LLMExtractor(call_fn=lambda _: "{}", cache_dir=None).prompt(NOTE, "new")
    assert "<note>\n" + NOTE + "\n</note>" in p and "Patient type: new" in p
    assert LEVEL_NAMES[2] == "low"
