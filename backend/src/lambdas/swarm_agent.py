# backend/src/lambdas/swarm_agent.py
"""SFN Map worker: one swarm agent = random profile -> Opus scenario -> execute loop.

Each invocation is an independent attacker persona. Findings stream to DynamoDB
under the shared scan_id (each tagged with its persona); the agent's profile +
scenario are stored as an AGENT# item. Exceptions are caught and recorded so one
agent's failure never fails the whole Map.
"""
from __future__ import annotations

import asyncio

from agents import llm_agent
from common import attacker_profile, scenario, store
from common.scope_guard import _load_allowlist


def handler(event, context):
    scan_id = event["scan_id"]
    target = event["target"]
    index = int(event.get("index", 0))
    try:
        profile = attacker_profile.generate()
        md, engine = scenario.generate_scenario(profile, target)
        store.put_agent(scan_id, index, profile, md, engine)

        def _stream(f):
            store.put_finding(scan_id, f.to_item())

        findings = asyncio.run(llm_agent.run(
            scan_id=scan_id, target=target["url"], endpoint=target["endpoint"],
            profile=profile, scenario=md, scope=_load_allowlist(),
            on_finding=_stream))
        return {"index": index, "finding_count": len(findings)}
    except Exception as exc:  # never fail the Map; record and move on
        store.put_agent(scan_id, index, {}, "", "error", error=str(exc)[:500])
        return {"index": index, "error": str(exc)[:500]}
