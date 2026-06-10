# backend/src/lambdas/execute_attack.py
"""SFN state: run the Opus-driven loop against the target, streaming findings."""
from __future__ import annotations

import asyncio

from agents import llm_agent
from common import store
from common.scope_guard import _load_allowlist


def handler(event, context):
    scan_id = event["scan_id"]
    target = event["target"]
    profile = event["profile"]
    scenario_md = event["scenario"]

    def _stream(finding):
        store.put_finding(scan_id, finding.to_item())

    findings = asyncio.run(llm_agent.run(
        scan_id=scan_id, target=target["url"], endpoint=target["endpoint"],
        profile=profile, scenario=scenario_md, scope=_load_allowlist(),
        on_finding=_stream))
    return {**event, "finding_count": len(findings)}
