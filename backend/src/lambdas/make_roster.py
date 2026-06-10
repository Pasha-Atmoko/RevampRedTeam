# backend/src/lambdas/make_roster.py
"""SFN state: turn the requested agent count into a roster list for the Map and
mark the job RUNNING. Clamps to [1, MAX_AGENTS]."""
from __future__ import annotations

from common import store

DEFAULT_AGENTS = 5
MAX_AGENTS = 8


def handler(event, context):
    scan_id = event["scan_id"]
    try:
        n = int(event.get("agents") or DEFAULT_AGENTS)
    except (TypeError, ValueError):
        n = DEFAULT_AGENTS
    n = max(1, min(MAX_AGENTS, n))
    store.update_job(scan_id, status="RUNNING", agent_count=n)
    return {**event, "roster": list(range(n)), "agent_count": n}
