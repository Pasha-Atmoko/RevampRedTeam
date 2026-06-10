"""Random attacker-profile generator.

This is step 1 of the backend flow: BEFORE asking Opus to write a pentest
scenario, we synthesize a *random adversary* to role-play. A profile is plain
data — an archetype plus randomized knobs (skill, motivation, stealth, toolset,
MITRE tactics) — that gets injected into the Opus prompt so each generated
scenario reads like it was authored by a different, plausible threat actor.

Inspired by the persona system in the reference `pentest-swarm` project, but
expanded into a fuller threat-actor profile suitable for scenario authoring.
"""
from __future__ import annotations

import random
import uuid

# --- vocabulary the generator samples from ----------------------------------

ARCHETYPES = [
    {"id": "ghost", "name": "The Ghost", "emoji": "\U0001F47B",
     "style": "stealthy and patient; minimizes noise, lives off the land"},
    {"id": "brute", "name": "The Brute", "emoji": "\U0001F528",
     "style": "loud and exhaustive; throws everything at the wall"},
    {"id": "trickster", "name": "The Trickster", "emoji": "\U0001F0CF",
     "style": "creative; obsessed with edge cases and protocol abuse"},
    {"id": "scholar", "name": "The Scholar", "emoji": "\U0001F393",
     "style": "methodical and precise; documents every step"},
    {"id": "shark", "name": "The Shark", "emoji": "\U0001F988",
     "style": "fast and ruthless; goes straight for high-impact targets"},
    {"id": "locksmith", "name": "The Locksmith", "emoji": "\U0001F511",
     "style": "auth & session specialist; picks every lock slowly"},
    {"id": "impersonator", "name": "The Impersonator", "emoji": "\U0001F3AD",
     "style": "identity bender; specializes in privilege escalation and IDOR"},
    {"id": "smuggler", "name": "The Smuggler", "emoji": "\U0001F4E6",
     "style": "protocol trickster; sneaks payloads past the front door"},
]

SKILL_LEVELS = [
    ("Script Kiddie", "relies on public tooling and known CVEs, little custom work"),
    ("Intermediate", "comfortable chaining known techniques and lightly customizing exploits"),
    ("Advanced", "writes custom tooling, chains novel bugs, careful about detection"),
    ("APT-grade", "nation-state tradecraft: bespoke implants, long dwell time, OPSEC-first"),
]

MOTIVATIONS = [
    "Financial gain (ransomware / data theft for resale)",
    "Hacktivism (defacement / leak to make a statement)",
    "Espionage (long-term intelligence collection)",
    "Thrill / reputation (bragging rights in the scene)",
    "Insider grudge (disgruntled ex-employee with prior knowledge)",
    "Supply-chain foothold (pivot to downstream victims)",
]

ORIGINS = [
    "Eastern Europe", "Southeast Asia", "South America", "West Africa",
    "domestic / on-shore", "unknown (proxied through Tor + bulletproof VPS)",
]

CREW_SIZES = [
    "Lone wolf", "Small crew (2-4)", "Organized cybercrime group",
    "State-sponsored team",
]

TTP_POOL = [
    "credential stuffing / password spraying",
    "JWT alg=none / weak-secret forgery",
    "IDOR / BOLA on object identifiers",
    "mass-assignment of privileged fields",
    "SQL / NoSQL injection",
    "SSRF to internal metadata services",
    "server-side template injection",
    "verbose-error fingerprinting",
    "rate-limit & lockout bypass",
    "session fixation / token replay",
    "content-type & parameter pollution",
    "directory/endpoint enumeration",
    "default / guessable credentials",
    "CORS misconfiguration abuse",
    "business-logic abuse (price/qty tampering)",
]

TOOL_POOL = [
    "Burp Suite Pro", "ffuf", "nuclei", "sqlmap", "nmap", "Hydra",
    "custom Python tooling", "jwt_tool", "Postman", "feroxbuster",
    "Metasploit", "wfuzz", "curl one-liners", "gobuster",
]

MITRE_TACTICS = [
    "TA0043 Reconnaissance", "TA0001 Initial Access", "TA0002 Execution",
    "TA0004 Privilege Escalation", "TA0005 Defense Evasion",
    "TA0006 Credential Access", "TA0007 Discovery",
    "TA0009 Collection", "TA0010 Exfiltration",
]

ADJ = ["silent", "crimson", "hollow", "iron", "feral", "midnight", "broken",
       "static", "rogue", "phantom", "zero", "null", "venom", "frost"]
NOUN = ["viper", "raven", "cipher", "wraith", "jackal", "monarch", "harbinger",
        "specter", "lynx", "kraken", "drifter", "oracle", "magpie"]


def _alias(rng: random.Random) -> str:
    return f"{rng.choice(ADJ)}_{rng.choice(NOUN)}{rng.randint(0, 99):02d}"


def generate(rng: random.Random | None = None) -> dict:
    """Synthesize a fresh, random attacker profile."""
    rng = rng or random.Random()
    arch = rng.choice(ARCHETYPES)
    skill_name, skill_desc = rng.choice(SKILL_LEVELS)
    stealth = round(rng.uniform(0.1, 0.95), 2)
    aggressiveness = round(1.0 - stealth + rng.uniform(-0.1, 0.1), 2)
    aggressiveness = max(0.05, min(0.98, aggressiveness))

    ttps = rng.sample(TTP_POOL, k=rng.randint(3, 5))
    tools = rng.sample(TOOL_POOL, k=rng.randint(3, 5))
    tactics = rng.sample(MITRE_TACTICS, k=rng.randint(3, 5))

    return {
        "id": uuid.uuid4().hex[:12],
        "alias": _alias(rng),
        "archetype": arch["name"],
        "archetype_id": arch["id"],
        "emoji": arch["emoji"],
        "style": arch["style"],
        "skill_level": skill_name,
        "skill_desc": skill_desc,
        "motivation": rng.choice(MOTIVATIONS),
        "origin": rng.choice(ORIGINS),
        "crew_size": rng.choice(CREW_SIZES),
        "stealth": stealth,            # 0 = loud, 1 = ghost
        "aggressiveness": aggressiveness,
        "preferred_ttps": ttps,
        "toolset": tools,
        "mitre_tactics": sorted(tactics),
    }


def to_prose(p: dict) -> str:
    """Render a profile as a compact prose block for the Opus prompt."""
    return (
        f"Alias: {p['alias']} ({p['emoji']} {p['archetype']})\n"
        f"Operating style: {p['style']}\n"
        f"Skill level: {p['skill_level']} — {p['skill_desc']}\n"
        f"Motivation: {p['motivation']}\n"
        f"Origin: {p['origin']}\n"
        f"Crew: {p['crew_size']}\n"
        f"Stealth: {p['stealth']} (0=loud, 1=ghost); "
        f"Aggressiveness: {p['aggressiveness']}\n"
        f"Preferred TTPs: {', '.join(p['preferred_ttps'])}\n"
        f"Toolset: {', '.join(p['toolset'])}\n"
        f"MITRE ATT&CK focus: {', '.join(p['mitre_tactics'])}"
    )
