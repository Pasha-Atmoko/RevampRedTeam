# backend/src/agents/llm_agent.py
"""Opus-driven pentest execution loop. Seeded with a random attacker profile and
the generated scenario; Opus decides each HTTP request, reads responses, adapts,
and reports findings. Scope-enforced and rate-limited.

Before the reasoning loop, a deterministic ENDPOINT DISCOVERY pass probes a
wordlist of common paths and feeds every live endpoint to Opus so it tests the
whole surface, not just the single seed path.
"""
from __future__ import annotations

import uuid
from typing import Callable

from common import bedrock
from common.http_client import AuditedClient
from common.models import Finding, Severity
from common.scope_guard import assert_in_scope

MAX_ITERATIONS = 22
MAX_REQUESTS = 60          # agent reasoning-loop budget (discovery is separate)
BODY_TRUNCATE = 1500
SEVERITIES = [s.value for s in Severity]

# Common web/API paths probed during the deterministic discovery pass. The seed
# endpoint is always included. A path is "live" if it returns anything but 404
# (and the host is reachable).
ENDPOINT_WORDLIST = [
    "/", "/login", "/register", "/logout", "/auth", "/signin", "/signup",
    "/api", "/api/login", "/api/register", "/api/auth", "/api/users", "/api/user",
    "/api/me", "/api/v1", "/api/v2", "/api/admin",
    "/admin", "/admin/login", "/dashboard", "/users", "/user", "/profile",
    "/account", "/settings", "/health", "/status", "/metrics", "/version",
    "/robots.txt", "/sitemap.xml", "/swagger.json", "/openapi.json", "/api-docs",
    "/v3/api-docs", "/.git/config", "/.env", "/config", "/debug", "/actuator",
    "/forgot-password", "/reset", "/token", "/refresh", "/upload", "/files",
    "/search", "/graphql",
]

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
         "path": {"type": "string",
                  "description": "the endpoint PATH this finding is on, e.g. '/api/users'"},
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

A discovery scan already found these LIVE endpoints on the target (path -> status):
{discovered}

Your job: test EVERY one of these endpoints (plus any new ones you find in \
responses) - do NOT stop after a single path. Work through the full list \
methodically: for each endpoint probe for auth/access-control flaws, injection, \
IDOR/BOLA, mass-assignment, info disclosure, and misconfig as appropriate.

Use the http_request tool (PATH only - it is joined to the authorized host; you \
cannot reach other hosts). ADAPT each request to the previous response. When you \
confirm or strongly suspect an issue, call report_finding (one call per issue) and \
set its `path` to the affected endpoint. You have at most {max_req} requests; \
spend them across ALL discovered endpoints, prioritizing high-impact checks. Never \
attempt denial-of-service or flooding. Reply with the single word DONE when finished."""


async def _discover_endpoints(client, target: str, seed: str) -> list[tuple[str, int]]:
    """Probe the wordlist (plus the seed) and return live (path, status) pairs."""
    seed = seed if seed.startswith("/") else "/" + seed
    paths = list(dict.fromkeys([seed, *ENDPOINT_WORDLIST]))  # dedupe, seed first
    live: list[tuple[str, int]] = []
    for p in paths:
        try:
            r = await client.request("GET", target + p)
        except Exception:
            continue
        code = getattr(r, "status_code", None)
        if code is not None and code != 404:
            live.append((p, code))
    return live


async def run(*, scan_id: str, target: str, endpoint: str, profile: dict,
              scenario: str, scope: list[str] | None,
              converse_fn: Callable[..., dict] | None = None,
              client_factory=AuditedClient,
              on_finding: Callable[[Finding], None] | None = None) -> list[Finding]:
    assert_in_scope(target, allowlist=scope)
    converse_fn = converse_fn or bedrock.converse
    plabel = f"{profile.get('archetype', 'actor')} ({profile.get('alias', '')})"
    seed = endpoint if endpoint.startswith("/") else "/" + endpoint

    findings: list[Finding] = []
    req_count = 0
    async with client_factory(scan_id) as client:
        # --- deterministic endpoint discovery (separate from the agent budget) ---
        discovered = await _discover_endpoints(client, target, seed)
        discovered_str = ("\n".join(f"  {p} -> {code}" for p, code in discovered)
                          or "  (none responded; recon from the seed path)")

        system = SYSTEM.format(
            alias=profile.get("alias", "operator"), archetype=profile.get("archetype", ""),
            style=profile.get("style", ""), skill=profile.get("skill_level", ""),
            target=target, scenario=scenario[:6000], max_req=MAX_REQUESTS,
            discovered=discovered_str)
        messages: list[dict] = [{"role": "user", "content": [{"type": "text",
            "text": f"Begin testing {target}. Discovered live endpoints:\n{discovered_str}\n"
                    f"Test all of them, starting with {seed}."}]}]

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
            path = inp.get("path") or seed
            if not path.startswith("/"):
                path = "/" + path
            f = Finding(scan_id=scan_id, finding_id=uuid.uuid4().hex,
                        title=inp.get("title", "(untitled)"), severity=sev,
                        endpoint=target + path, evidence=inp.get("evidence", ""),
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
