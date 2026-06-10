# backend/src/common/bedrock.py
"""Amazon Bedrock wrapper. Defaults to Claude Opus for deep reasoning.

invoke_opus  -> single-turn text (scenario authoring)
converse     -> one turn of the Converse API with tools (the Opus attack loop)
"""
from __future__ import annotations

import json
import os
from functools import lru_cache

import boto3

OPUS = os.environ.get("BEDROCK_OPUS_MODEL", "us.anthropic.claude-opus-4-5-20251101-v1:0")
AWS_REGION = os.environ.get("AWS_REGION", "us-east-1")


class BedrockUnavailable(Exception):
    """Raised when Bedrock cannot be reached / is not configured."""


@lru_cache(maxsize=1)
def _client():
    return boto3.client("bedrock-runtime", region_name=AWS_REGION)


def invoke_opus(system: str, user: str, max_tokens: int = 4096,
                temperature: float = 0.7) -> str:
    body = {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens, "temperature": temperature, "system": system,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
    }
    try:
        resp = _client().invoke_model(modelId=OPUS, body=json.dumps(body))
        payload = json.loads(resp["body"].read())
    except Exception as exc:
        raise BedrockUnavailable(str(exc)) from exc
    return "".join(b.get("text", "") for b in payload.get("content", [])
                   if b.get("type") == "text")


def _to_bedrock_content(block: dict) -> dict:
    t = block["type"]
    if t == "text":
        return {"text": block["text"]}
    if t == "tool_use":
        return {"toolUse": {"toolUseId": block["id"], "name": block["name"],
                            "input": block.get("input", {})}}
    if t == "tool_result":
        return {"toolResult": {"toolUseId": block["tool_use_id"],
                               "content": [{"json": block["output"]}], "status": "success"}}
    raise ValueError(f"unknown block type {t!r}")


def converse(messages: list[dict], system: str, tools: list[dict],
             model_id: str = OPUS, max_tokens: int = 1024) -> dict:
    bedrock_messages = [{"role": m["role"],
                         "content": [_to_bedrock_content(b) for b in m["content"]]}
                        for m in messages]
    tool_config = {"tools": [{"toolSpec": {"name": t["name"], "description": t["description"],
                   "inputSchema": {"json": t["schema"]}}} for t in tools]}
    resp = _client().converse(
        modelId=model_id, messages=bedrock_messages, system=[{"text": system}],
        toolConfig=tool_config,
        inferenceConfig={"maxTokens": max_tokens, "temperature": 0.0})
    out_blocks = []
    for blk in resp["output"]["message"]["content"]:
        if "text" in blk:
            out_blocks.append({"type": "text", "text": blk["text"]})
        elif "toolUse" in blk:
            tu = blk["toolUse"]
            out_blocks.append({"type": "tool_use", "id": tu["toolUseId"],
                               "name": tu["name"], "input": tu.get("input", {})})
    stop = "tool_use" if resp.get("stopReason") == "tool_use" else "end"
    return {"stop": stop, "blocks": out_blocks}
