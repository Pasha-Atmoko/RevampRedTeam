# backend/src/lambdas/get_scan.py
"""GET /scan/{id} : return the job meta + findings."""
from __future__ import annotations

import json

from common import store

CORS = {"Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "content-type,x-api-key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json"}


def _resp(code: int, body: dict) -> dict:
    return {"statusCode": code, "headers": CORS, "body": json.dumps(body, default=str)}


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return _resp(200, {})
    scan_id = (event.get("pathParameters") or {}).get("id", "")
    if not scan_id:
        return _resp(400, {"error": "missing scan id"})
    job = store.get_scan(scan_id)
    if job is None:
        return _resp(404, {"error": "scan not found"})
    return _resp(200, job)
