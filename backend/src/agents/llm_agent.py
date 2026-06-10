# backend/src/agents/llm_agent.py
"""Opus-driven pentest execution loop. Seeded with a random attacker profile and
the generated scenario; Opus decides each HTTP request, reads responses, adapts,
and reports findings. Scope-enforced and rate-limited."""
from __future__ import annotations

import uuid
from typing import Callable

from common import bedrock
from common.http_client import AuditedClient
from common.models import Finding, Severity
from common.scope_guard import assert_in_scope

MAX_ITERATIONS = 14
MAX_REQUESTS = 24
BODY_TRUNCATE = 1500
SEVERITIES = [s.value for s in Severity]

TOOLS = [
    {"name": "http_request",
     "description": "Send one HTTP request to the authorized target. Provide a PATH "
                    "(e.g. '/login'); it is joined to the target host. Returns status, "
                    "selected headers, and a truncated body.",
     "schema": {"type": "object", "properties": {
         "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
         "path": {"type": "string"},
         "json_body": {"type": "object"},
         "headers": {"type": "object"}}, "required": ["method", "path"]}},
    {"name": "report_finding",
     "description": "Record a confirmed or strongly-suspected vulnerability.",
     "schema": {"type": "object", "properties": {
         "title": {"type": "string"},
         "severity": {"type": "string", "enum": SEVERITIES},
         "attack_method": {"type": "string"},
         "evidence": {"type": "string"},
         "poc": {"type": "string"},
         "remediation": {"type": "string"}},
         "required": ["title", "severity", "attack_method", "evidence"]}},
]

SYSTEM = """You are {alias} ({archetype}), an autonomous API penetration tester with \
WRITTEN AUTHORIZATION to test {target}. Your style: {style}. Skill: {skill}.

Follow THIS pentest scenario you authored (stay in character, adapt to responses):
---
{scenario}
---

Begin at {target}{endpoint}. Use the http_request tool (PATH only - it is joined to \
the authorized host; you cannot reach other hosts). ADAPT each next request to the \
previous response - do not follow a fixed script. When you confirm or strongly \
suspect an issue, call report_finding (one call per issue). You have at most \
{max_req} requests; prioritize high-impact checks. Never attempt denial-of-service \
or flooding. Reply with the single word DONE when finished."""


async def run(*, scan_id: str, target: str, endpoint: str, profile: dict,
              scenario: str, scope: list[str] | None,
              converse_fn: Callable[..., dict] | None = None,
              client_factory=AuditedClient,
              on_finding: Callable[[Finding], None] | None = None) -> list[Finding]:
    assert_in_scope(target, allowlist=scope)
    converse_fn = converse_fn or bedrock.converse
    plabel = f"{profile.get('archetype', 'actor')} ({profile.get('alias', '')})"

    findings: list[Finding] = []
    system = SYSTEM.format(
        alias=profile.get("alias", "operator"), archetype=profile.get("archetype", ""),
        style=profile.get("style", ""), skill=profile.get("skill_level", ""),
        target=target, endpoint=endpoint if endpoint.startswith("/") else "/" + endpoint,
        scenario=scenario[:6000], max_req=MAX_REQUESTS)
    messages: list[dict] = [{"role": "user", "content": [
        {"type": "text", "text": f"Begin testing {target}{endpoint}. Start with recon."}]}]

    req_count = 0
    async with client_factory(scan_id) as client:
        async def do_http(inp: dict) -> dict:
            nonlocal req_count
            if req_count >= MAX_REQUESTS:
                return {"error": "request budget exhausted"}
            req_count += 1
            path = inp.get("path", "/")
            if not path.startswith("/"):
                path = "/" + path
            try:
                r = await client.request(inp.get("method", "GET"), target + path,
                                         json=inp.get("json_body"),
                                         headers=inp.get("headers") or None)
            except Exception as exc:
                return {"error": str(exc)}
            return {"status": r.status_code,
                    "headers": {k: v for k, v in r.headers.items()
                                if k.lower() in ("content-type",
                                                 "access-control-allow-origin",
                                                 "www-authenticate", "server")},
                    "body": r.text[:BODY_TRUNCATE]}

        def do_report(inp: dict) -> dict:
            try:
                sev = Severity(inp.get("severity", "info"))
            except ValueError:
                sev = Severity.INFO
            f = Finding(scan_id=scan_id, finding_id=uuid.uuid4().hex,
                        title=inp.get("title", "(untitled)"), severity=sev,
                        endpoint=target + endpoint, evidence=inp.get("evidence", ""),
                        poc=inp.get("poc", ""), remediation=inp.get("remediation", ""),
                        attack_method=inp.get("attack_method", ""), persona=plabel)
            findings.append(f)
            if on_finding:
                on_finding(f)
            return {"recorded": True}

        for _ in range(MAX_ITERATIONS):
            turn = converse_fn(messages, system, TOOLS, model_id=bedrock.OPUS)
            blocks = turn.get("blocks", [])
            messages.append({"role": "assistant", "content": blocks})
            tool_uses = [b for b in blocks if b["type"] == "tool_use"]
            if turn.get("stop") != "tool_use" or not tool_uses:
                break
            results = []
            for tu in tool_uses:
                if tu["name"] == "http_request":
                    output = await do_http(tu.get("input", {}))
                elif tu["name"] == "report_finding":
                    output = do_report(tu.get("input", {}))
                else:
                    output = {"error": f"unknown tool {tu['name']}"}
                results.append({"type": "tool_result", "tool_use_id": tu["id"],
                                "output": output})
            messages.append({"role": "user", "content": results})
            if req_count >= MAX_REQUESTS:
                messages.append({"role": "user", "content": [{"type": "text",
                    "text": "Request budget exhausted. Report remaining findings and say DONE."}]})
    return findings
