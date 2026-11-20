from safe_to_bill.mdm import CODES, Element, data_level, mdm_level, problems_level, risk_level, score


def d(t, name=""):
    return Element("data", t, name, "q")


def test_two_of_three_rule():
    assert mdm_level(3, 1, 3) == 3
    assert mdm_level(2, 1, 3) == 2          # one moderate element is not enough
    assert mdm_level(4, 2, 4) == 4
    assert mdm_level(4, 4, 1) == 4
    assert mdm_level(1, 1, 2) == 1
    assert mdm_level(3, 4, 2) == 3


def test_problem_counting():
    assert problems_level([]) == 1
    assert problems_level(["self_limited_minor"]) == 1
    assert problems_level(["self_limited_minor", "self_limited_minor"]) == 2
    assert problems_level(["stable_chronic"]) == 2
    assert problems_level(["stable_chronic", "stable_chronic"]) == 3
    assert problems_level(["acute_uncomplicated", "threat_to_life_or_function"]) == 4


def test_ordering_includes_review_so_a_test_counts_once():
    items = [d("order_test", "Chest X-ray"), d("review_test_result", "chest x-ray")]
    assert data_level(items) == 1


def test_data_levels():
    assert data_level([d("order_test", "ua"), d("order_test", "culture")]) == 2
    assert data_level([d("independent_historian")]) == 2
    assert data_level([d("order_test", "a"), d("order_test", "b"), d("independent_historian")]) == 3
    assert data_level([d("independent_interpretation")]) == 3
    assert data_level([d("order_test", "x"), d("independent_interpretation"), d("discussion_external")]) == 4
    assert data_level([d("review_external_note", "pcp"), d("review_external_note", "PCP")]) == 1


def test_risk_is_the_highest_item():
    assert risk_level([]) == 1
    assert risk_level(["low_risk", "prescription_drug_management"]) == 3
    assert risk_level(["minimal_risk", "hospitalization_or_escalation"]) == 4


def test_score_and_codes():
    els = [Element("problem", "acute_uncomplicated", "uti", "q"),
           Element("risk", "prescription_drug_management", "rx", "q")]
    r = score(els)
    assert (r.problems, r.data, r.risk, r.level) == (2, 1, 3, 2)
    assert r.code("new") == "99203" and r.code("established") == "99213"
    assert CODES["new"][4] == "99205" and CODES["established"][1] == "99212"
