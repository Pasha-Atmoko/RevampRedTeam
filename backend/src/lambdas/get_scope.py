# backend/src/lambdas/get_scope.py
"""GET /scope : return the current authorized target allowlist.

Lets the frontend populate a dropdown of permitted targets instead of making the
operator type ip/port by hand. Reads the same SSM allowlist the scope guard uses.
"""
from __future__ import annotations

import json

from common.scope_guard import _load_allowlist

CORS = {"Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "content-type,x-api-key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json"}


def _resp(code: int, body: dict) -> dict:
    return {"statusCode": code, "headers": CORS, "body": json.dumps(body)}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return _resp(200, {})
    try:
        targets = _load_allowlist()
    except Exception as exc:           # param missing / SSM error -> empty, not 500
        return _resp(200, {"targets": [], "error": str(exc)})
    return _resp(200, {"targets": targets})
