# backend/tests/test_scenario.py
import random
from common import attacker_profile, scenario, bedrock


def _target():
    return {"ip": "1.2.3.4", "port": 8080, "endpoint": "/login",
            "url": "http://1.2.3.4:8080"}


def test_offline_fallback_when_bedrock_unavailable(monkeypatch):
    def boom(*a, **k):
        raise bedrock.BedrockUnavailable("no creds")
    monkeypatch.setattr(scenario.bedrock, "invoke_opus", boom)
    p = attacker_profile.generate(random.Random(1))
    md, engine = scenario.generate_scenario(p, _target())
    assert engine == "offline-sim"
    assert "Offline simulation" in md
    assert "/login" in md


def test_uses_opus_when_available(monkeypatch):
    monkeypatch.setattr(scenario.bedrock, "invoke_opus",
                        lambda system, user, **k: "# Real Opus scenario\nbody")
    p = attacker_profile.generate(random.Random(1))
    md, engine = scenario.generate_scenario(p, _target())
    assert engine == "bedrock-opus"
    assert md.startswith("# Real Opus scenario")
