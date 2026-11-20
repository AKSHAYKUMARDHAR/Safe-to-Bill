from safe_to_bill.decide import decide
from safe_to_bill.mdm import Element
from safe_to_bill.verify import normalize, quote_in_note, verify

NOTE = "Rapid strep ordered: negative.\nAssessment: viral   pharyngitis.\nPlan: ibuprofen OTC."


def test_normalize_and_quotes():
    assert normalize("  Viral\n PHARYNGITIS. ") == "viral pharyngitis"
    assert quote_in_note("assessment: viral pharyngitis", NOTE)
    assert quote_in_note("Rapid strep ordered ... ibuprofen OTC", NOTE)
    assert not quote_in_note("ibuprofen OTC ... Rapid strep", NOTE)  # parts must be in order
    assert not quote_in_note("amoxicillin prescribed", NOTE)
    assert not quote_in_note("", NOTE)


def test_stitched_sentences_pass_only_in_order_and_long_enough():
    note = ("57M with asthma, wheezing for 2 days after a cold. SpO2 96%, mild wheezes.\n"
            "Assessment: mild asthma exacerbation.\nPlan: prednisone prescribed.")
    stitched = "57M with asthma, wheezing for 2 days after a cold. Assessment: mild asthma exacerbation."
    assert quote_in_note(stitched, note)                       # real sentences, text between skipped
    assert not quote_in_note("Assessment: mild asthma exacerbation. 57M with asthma, wheezing for 2 days.", note)
    assert not quote_in_note("57M with asthma, wheezing for 2 days after a cold. No.", note)  # too short
    assert not quote_in_note("57M with asthma. Assessment: severe asthma exacerbation.", note)  # altered text


def test_verify_drops_invented_quotes():
    good = Element("problem", "acute_uncomplicated", "pharyngitis", "viral pharyngitis")
    bad = Element("risk", "prescription_drug_management", "amox", "amoxicillin 500 mg prescribed")
    kept, dropped = verify([good, bad], NOTE)
    assert kept == [good] and dropped == [bad]


def test_decisions():
    assert decide("99213", "established", 2, True).action == "BILL"
    over = decide("99214", "established", 2, True)
    assert (over.action, over.reason, over.supported_code) == ("HOLD", "overcoded", "99213")
    assert decide("99203", "new", 3, True).reason == "undercoded"
    assert decide("99213", "established", 2, False, "runs disagree").reason == "not_confident"
    assert decide("99203", "established", 2, True).reason == "wrong_family"
    assert decide("99285", "new", 2, True).reason == "unsupported_code"


def test_copy_forward_problems_are_not_counted_in_v3():
    from safe_to_bill.verify import verify as v
    note = ("PMH (carried forward from prior visit): HTN, DM2; not addressed today.\n"
            "A/P: acute bronchitis. Benzonatate prescribed.")
    old = Element("problem", "stable_chronic", "htn", "PMH (carried forward from prior visit): HTN, DM2; not addressed today.")
    new = Element("problem", "acute_uncomplicated", "bronchitis", "A/P: acute bronchitis.")
    assert v([old, new], note, "v2")[0] == [old, new]
    assert v([old, new], note, "v3") == ([new], [old])
    hist = Element("problem", "chronic_exacerbation", "migraine", "33F with a history of migraines")
    assert v([hist], "33F with a history of migraines, worse this week.", "v3")[0] == [hist]
