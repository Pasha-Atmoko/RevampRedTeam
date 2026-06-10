# backend/tests/test_llm_agent.py
import asyncio
from agents import llm_agent


class FakeResponse:
    def __init__(self, status=200, text="{}", headers=None):
        self.status_code = status
        self.text = text
        self.headers = headers or {}


class FakeClient:
    def __init__(self, *a, **k):
        self.calls = []

    async def __aenter__(self):
        return self

    async def __aexit__(self, *e):
        return False

    async def request(self, method, url, **kw):
        self.calls.append((method, url))
        return FakeResponse(200, '{"ok": true}', {"server": "test"})


def make_converse_script():
    """Turn 1: GET /login. Turn 2: report a finding. Turn 3: DONE."""
    state = {"n": 0}

    def fn(messages, system, tools, model_id=None, max_tokens=1024):
        state["n"] += 1
        if state["n"] == 1:
            return {"stop": "tool_use", "blocks": [
                {"type": "tool_use", "id": "t1", "name": "http_request",
                 "input": {"method": "GET", "path": "/login"}}]}
        if state["n"] == 2:
            return {"stop": "tool_use", "blocks": [
                {"type": "tool_use", "id": "t2", "name": "report_finding",
                 "input": {"title": "Weak login", "severity": "high",
                           "attack_method": "cred brute", "evidence": "200 ok"}}]}
        return {"stop": "end", "blocks": [{"type": "text", "text": "DONE"}]}
    return fn


def test_loop_executes_requests_and_records_findings():
    recorded = []
    findings = asyncio.run(llm_agent.run(
        scan_id="s1", target="http://1.2.3.4:8080", endpoint="/login",
        profile={"alias": "ghost01", "archetype": "The Ghost", "style": "stealthy",
                 "skill_level": "Advanced", "preferred_ttps": ["x"],
                 "aggressiveness": 0.3, "stealth": 0.8},
        scenario="# scenario\nattack the login",
        scope=["1.2.3.4:8080"],
        converse_fn=make_converse_script(),
        client_factory=FakeClient,
        on_finding=recorded.append,
    ))
    assert len(findings) == 1
    assert findings[0].title == "Weak login"
    assert findings[0].severity.value == "high"
    assert recorded and recorded[0].title == "Weak login"  # streamed via callback


def test_loop_blocks_out_of_scope():
    import pytest
    from common.scope_guard import ScopeError
    with pytest.raises(ScopeError):
        asyncio.run(llm_agent.run(
            scan_id="s1", target="http://9.9.9.9:80", endpoint="/",
            profile={"alias": "x", "archetype": "y", "style": "z",
                     "skill_level": "a", "preferred_ttps": [], "aggressiveness": 0.5,
                     "stealth": 0.5},
            scenario="x", scope=["1.2.3.4:8080"],
            converse_fn=make_converse_script(), client_factory=FakeClient))
