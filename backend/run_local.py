#!/usr/bin/env python3
"""Run profile -> scenario -> Opus loop in-process (no AWS). Offline-sim if no Bedrock.

Usage:
  python run_local.py http://1.2.3.4:8080 --endpoint /login --scope 1.2.3.4:8080 --yes
"""
import argparse
import asyncio
import sys
import uuid

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

sys.path.insert(0, "src")

from agents import llm_agent  # noqa: E402
from common import attacker_profile, scenario  # noqa: E402
from common.scope_guard import ScopeError, assert_in_scope  # noqa: E402


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("target")
    ap.add_argument("--endpoint", default="/")
    ap.add_argument("--scope", nargs="+", required=True)
    ap.add_argument("--yes", action="store_true", help="confirm authorization")
    args = ap.parse_args()
    if not args.yes:
        print("Refusing to run without --yes (authorization confirmation).")
        return 2
    try:
        assert_in_scope(args.target, allowlist=args.scope)
    except ScopeError as exc:
        print(f"SCOPE ERROR: {exc}")
        return 2

    scan_id = uuid.uuid4().hex
    profile = attacker_profile.generate()
    target = {"ip": args.target.split("//")[-1].split(":")[0],
              "port": args.target.rsplit(":", 1)[-1], "endpoint": args.endpoint,
              "url": args.target.rstrip("/")}
    print(f"\n# Attacker profile\n{attacker_profile.to_prose(profile)}\n")
    md, engine = scenario.generate_scenario(profile, target)
    print(f"# Scenario (engine={engine})\n{md}\n")
    findings = await llm_agent.run(
        scan_id=scan_id, target=target["url"], endpoint=args.endpoint,
        profile=profile, scenario=md, scope=args.scope)
    print(f"\n# Findings ({len(findings)})")
    for f in sorted(findings, key=lambda x: x.severity.rank, reverse=True):
        print(f"## [{f.severity.value.upper()}] {f.title} - {f.attack_method}")
        print(f"- evidence: {f.evidence}\n- fix: {f.remediation}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
