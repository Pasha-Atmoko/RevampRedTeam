# backend/tests/test_lambdas_states.py
from lambdas import validate_scope, profile_and_scenario


def test_validate_scope_passes_in_scope(monkeypatch):
    monkeypatch.setattr(validate_scope, "_scope", lambda: ["1.2.3.4:8080"])
    monkeypatch.setattr(validate_scope.store, "update_job", lambda *a, **k: None)
    event = {"scan_id": "s1",
             "target": {"ip": "1.2.3.4", "port": 8080, "endpoint": "/login",
                        "url": "http://1.2.3.4:8080"}}
    out = validate_scope.handler(event, None)
    assert out["in_scope"] is True


def test_validate_scope_rejects(monkeypatch):
    updates = {}
    monkeypatch.setattr(validate_scope, "_scope", lambda: ["1.2.3.4:8080"])
    monkeypatch.setattr(validate_scope.store, "update_job",
                        lambda sid, **k: updates.update(k))
    event = {"scan_id": "s1",
             "target": {"ip": "9.9.9.9", "port": 80, "endpoint": "/",
                        "url": "http://9.9.9.9:80"}}
    import pytest
    with pytest.raises(Exception):
        validate_scope.handler(event, None)
    assert updates.get("status") == "REJECTED"


def test_profile_and_scenario_persists(monkeypatch):
    saved = {}
    monkeypatch.setattr(profile_and_scenario.store, "update_job",
                        lambda sid, **k: saved.update(k))
    monkeypatch.setattr(profile_and_scenario.scenario, "generate_scenario",
                        lambda p, t: ("# scenario", "offline-sim"))
    event = {"scan_id": "s1",
             "target": {"ip": "1.2.3.4", "port": 8080, "endpoint": "/login",
                        "url": "http://1.2.3.4:8080"}}
    out = profile_and_scenario.handler(event, None)
    assert saved["status"] == "RUNNING"
    assert saved["engine"] == "offline-sim"
    assert out["profile"]["alias"]
    assert out["scenario"] == "# scenario"
