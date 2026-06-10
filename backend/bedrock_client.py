"""Amazon Bedrock client wrapper — forced to Claude Opus for scenario authoring.

Step 2 of the backend flow: given a random attacker profile + a target, ask
Opus (the deepest-reasoning Claude on Bedrock) to author a tailored pentest
scenario. Adapted from the reference `pentest-swarm/src/common/bedrock.py`.

Claude 4.x on Bedrock requires a cross-region INFERENCE PROFILE id (the "us."
prefix), not the raw on-demand model id (which raises ValidationException).
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

import boto3

# Opus inference profile. Override via env if your region/account differs.
OPUS_MODEL = os.environ.get(
    "BEDROCK_OPUS_MODEL", "us.anthropic.claude-opus-4-5-20251101-v1:0"
)
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


class BedrockUnavailable(Exception):
    """Raised when Bedrock cannot be reached / is not configured."""


@lru_cache(maxsize=1)
def _client():
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def invoke_opus(
    system: str,
    user: str,
    max_tokens: int = 4096,
    temperature: float = 0.7,
) -> str:
    """Single-turn invoke against Claude Opus. Returns the assistant's text.

    Raises BedrockUnavailable on any client/credential/region error so the
    caller can fall back to offline mode.
    """
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
    }
    try:
        resp = _client().invoke_model(modelId=OPUS_MODEL, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
    except Exception as exc:  # boto/credential/region/access errors
        raise BedrockUnavailable(str(exc)) from exc

    return "".join(
        block.get("text", "")
        for block in payload.get("content", [])
        if block.get("type") == "text"
    )
