# backend/tests/test_attacker_profile.py
import random
from common import attacker_profile


def test_generate_has_all_fields():
    p = attacker_profile.generate(random.Random(1))
    for key in ("id", "alias", "archetype", "skill_level", "motivation",
                "origin", "crew_size", "stealth", "aggressiveness",
                "preferred_ttps", "toolset", "mitre_tactics"):
        assert key in p, f"missing {key}"
    assert 0.0 <= p["stealth"] <= 1.0
    assert len(p["preferred_ttps"]) >= 3


def test_seeded_rng_is_reproducible():
    a = attacker_profile.generate(random.Random(42))
    b = attacker_profile.generate(random.Random(42))
    assert a == b


def test_to_prose_mentions_alias():
    p = attacker_profile.generate(random.Random(7))
    assert p["alias"] in attacker_profile.to_prose(p)
