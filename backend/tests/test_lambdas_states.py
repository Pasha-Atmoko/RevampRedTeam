# backend/tests/test_lambdas_states.py
from lambdas import validate_scope, profile_and_scenario, make_roster, swarm_agent


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


def test_make_roster_clamps_and_defaults(monkeypatch):
    monkeypatch.setattr(make_roster.store, "update_job", lambda *a, **k: None)
    out = make_roster.handler({"scan_id": "s1", "agents": 99}, None)
    assert out["roster"] == list(range(8))          # capped at 8
    assert out["agent_count"] == 8
    assert make_roster.handler({"scan_id": "s1"}, None)["agent_count"] == 5  # default


def test_swarm_agent_stores_persona_and_streams(monkeypatch):
    saved = {}
    monkeypatch.setattr(swarm_agent.attacker_profile, "generate",
                        lambda: {"alias": "a", "archetype": "X", "skill_level": "Adv"})
    monkeypatch.setattr(swarm_agent.scenario, "generate_scenario",
                        lambda p, t: ("# s", "offline-sim"))
    monkeypatch.setattr(swarm_agent.store, "put_agent",
                        lambda sid, idx, *a, **k: saved.update({"agent_idx": idx}))
    monkeypatch.setattr(swarm_agent.store, "put_finding", lambda *a, **k: None)
    monkeypatch.setattr(swarm_agent, "_load_allowlist", lambda: ["1.2.3.4:80"])

    async def fake_run(**kw):
        return ["f1", "f2"]
    monkeypatch.setattr(swarm_agent.llm_agent, "run", fake_run)

    out = swarm_agent.handler(
        {"scan_id": "s1", "index": 2,
         "target": {"url": "http://1.2.3.4:80", "endpoint": "/"}}, None)
    assert out["index"] == 2
    assert out["finding_count"] == 2
    assert saved["agent_idx"] == 2
