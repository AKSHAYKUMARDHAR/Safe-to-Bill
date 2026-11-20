import json

from fastapi.testclient import TestClient

NOTE = ("19F, sore throat x2 days. Rapid strep ordered: negative.\nAssessment: viral pharyngitis.\n"
        "Plan: salt-water gargles, ibuprofen OTC.")


def _client(tmp_path, monkeypatch):
    monkeypatch.setenv("EVENT_LOG", str(tmp_path / "events.jsonl"))
    import importlib

    import api.main as m
    importlib.reload(m)
    return TestClient(m.app), tmp_path / "events.jsonl"


def test_check_bills_and_logs_without_note_text(tmp_path, monkeypatch):
    client, log = _client(tmp_path, monkeypatch)
    r = client.post("/check", json={"note": NOTE, "patient_type": "established",
                                    "billed_code": "99213", "pipeline": "rules"})
    assert r.status_code == 200
    body = r.json()
    assert body["decision"]["action"] == "BILL"
    assert all(e["quote"].lower() in NOTE.lower() for e in body["elements"])
    event = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert "note" not in event and len(event["note_sha256"]) == 64 and "pharyngitis" not in json.dumps(event)


def test_overcoded_is_held_and_stats_count_it(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/check", json={"note": NOTE, "patient_type": "established",
                                    "billed_code": "99215", "pipeline": "rules"})
    assert r.json()["decision"]["reason"] == "overcoded"
    s = client.get("/stats").json()
    assert s["checks"] == 1 and s["actions"] == {"HOLD": 1}


def test_bad_input_is_rejected(tmp_path, monkeypatch):
    client, _ = _client(tmp_path, monkeypatch)
    r = client.post("/check", json={"note": "short", "patient_type": "x", "billed_code": "abc"})
    assert r.status_code == 422
    assert client.get("/health").json()["status"] == "ok"
