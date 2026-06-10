# backend/src/common/scenario.py
"""Pentest-scenario authoring: random attacker profile + target -> Opus scenario,
with a deterministic offline fallback so the pipeline completes without Bedrock."""
from __future__ import annotations

from common import attacker_profile, bedrock

SYSTEM = """You are a senior offensive-security engineer writing a penetration-\
test SCENARIO for an AUTHORIZED, scoped engagement (the client owns the target \
and signed a rules-of-engagement document).

You are given (a) a randomly generated threat-actor profile to role-play and \
(b) a single authorized target. Author a realistic, professional pentest scenario \
this actor would run against this target, in the actor's voice and style.

Produce a planning artifact, NOT live weaponized exploits: methodology, attack \
narrative, what is probed and why, expected indicators, and detection/remediation. \
No ready-to-run destructive payloads; never describe denial-of-service or flooding.

Return GitHub-flavored Markdown with these sections in order:
1. Scenario Overview (2-3 sentences)
2. Threat Actor Snapshot (bulleted)
3. Attack Narrative (numbered phases: Recon -> Initial Access -> Priv-Esc/Lateral -> Objective), tied to the endpoint/port and the actor's TTPs
4. MITRE ATT&CK Mapping (markdown table: Tactic | Technique | Where in scenario)
5. Expected Indicators & Detection
6. Remediation Priorities (ranked)
Keep it ~600-900 words."""


def _user_prompt(profile: dict, target: dict) -> str:
    return ("## Randomly generated threat-actor profile\n"
            f"{attacker_profile.to_prose(profile)}\n\n"
            "## Authorized target\n"
            f"- IP: {target['ip']}\n- Port: {target['port']}\n"
            f"- Endpoint: {target['endpoint']}\n- Base URL: {target['url']}\n\n"
            "Author the pentest scenario for THIS actor against THIS target.")


def generate_scenario(profile: dict, target: dict) -> tuple[str, str]:
    """Return (markdown, engine) where engine is 'bedrock-opus' or 'offline-sim'."""
    try:
        md = bedrock.invoke_opus(SYSTEM, _user_prompt(profile, target))
        if md.strip():
            return md, "bedrock-opus"
    except bedrock.BedrockUnavailable:
        pass
    return _offline_scenario(profile, target), "offline-sim"


def _offline_scenario(profile: dict, target: dict) -> str:
    p, t = profile, target
    ttps = "\n".join(f"   - {x}" for x in p["preferred_ttps"])
    rows = "\n".join(f"| {tac} | (actor tooling) | Phase {i + 1} |"
                     for i, tac in enumerate(p["mitre_tactics"]))
    return f"""> **Offline simulation** - Bedrock/Opus unreachable; locally templated, not live Opus output.

# Pentest Scenario - {p['emoji']} {p['archetype']} vs `{t['url']}`

## 1. Scenario Overview
**{p['alias']}** ({p['archetype']}, {p['skill_level']}) targets `{t['url']}` endpoint
`{t['endpoint']}` driven by: {p['motivation']}. Style: {p['style']}.

## 2. Threat Actor Snapshot
- Alias: {p['alias']}
- Skill: {p['skill_level']} - {p['skill_desc']}
- Origin / crew: {p['origin']} / {p['crew_size']}
- Stealth / aggressiveness: {p['stealth']} / {p['aggressiveness']}
- Toolset: {', '.join(p['toolset'])}

## 3. Attack Narrative
1. Recon - fingerprint `{t['ip']}:{t['port']}`, enumerate around `{t['endpoint']}`.
2. Initial Access - preferred TTPs against `{t['endpoint']}`:
{ttps}
3. Privilege Escalation / Lateral - pivot toward privileged identities.
4. Objective - pursue {p['motivation']}.

## 4. MITRE ATT&CK Mapping
| Tactic | Technique | Where in scenario |
|--------|-----------|-------------------|
{rows}

## 5. Expected Indicators & Detection
- 4xx/401/403 spikes around `{t['endpoint']}`; anomalous user-agents; unusual object-id access.

## 6. Remediation Priorities
1. Enforce authn/authz + object-level checks on `{t['endpoint']}`.
2. Rate-limit credential abuse; remove default creds.
3. Generic errors; hide stack traces.
4. Alert on the indicators above.
"""
