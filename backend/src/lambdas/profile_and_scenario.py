# backend/src/lambdas/profile_and_scenario.py
"""SFN state: generate a RANDOM attacker profile, then an Opus pentest scenario."""
from __future__ import annotations

from common import attacker_profile, scenario, store


def handler(event, context):
    scan_id = event["scan_id"]
    target = event["target"]
    profile = attacker_profile.generate()
    md, engine = scenario.generate_scenario(profile, target)
    store.update_job(scan_id, status="RUNNING", profile=profile, scenario=md,
                     engine=engine)
    return {**event, "profile": profile, "scenario": md, "engine": engine}
