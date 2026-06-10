# backend/src/lambdas/submit_scan.py
"""POST /scan : validate input, create a job, start the Step Functions execution."""
from __future__ import annotations

import ipaddress
import json
import os
import uuid

import boto3

from common import store
from common.models import Target

STATE_MACHINE_ARN = os.environ.get("STATE_MACHINE_ARN", "")

_sfn = boto3.client("stepfunctions")

CORS = {"Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Headers": "content-type,x-api-key",
        "Access-Control-Allow-Methods": "GET,POST,OPTIONS",
        "Content-Type": "application/json"}


def _resp(code: int, body: dict) -> dict:
    return {"statusCode": code, "headers": CORS, "body": json.dumps(body)}


def _validate(data: dict) -> str | None:
    if data.get("authorized") is not True:
        return "Field 'authorized' must be true (you must confirm authorization)."
    ip = str(data.get("ip", "")).strip()
    if not ip:
        return "Field 'ip' is required."
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        if not all(c.isalnum() or c in ".-" for c in ip):
            return "Field 'ip' is not a valid IP or hostname."
    try:
        port = int(data.get("port"))
    except (TypeError, ValueError):
        return "Field 'port' must be an integer."
    if not (1 <= port <= 65535):
        return "Field 'port' must be between 1 and 65535."
    ep = str(data.get("endpoint", "/"))
    if not ep.startswith("/"):
        return "Field 'endpoint' must start with '/'."
    return None


def handler(event, context):
    if event.get("httpMethod") == "OPTIONS":
        return _resp(200, {})
    try:
        data = json.loads(event.get("body") or "{}")
    except json.JSONDecodeError:
        return _resp(400, {"error": "Body must be valid JSON."})
    err = _validate(data)
    if err:
        return _resp(400, {"error": err})

    target = Target.from_parts(data["ip"], data["port"], data.get("endpoint", "/"))
    scan_id = uuid.uuid4().hex
    store.create_job(scan_id, target.to_dict())
    _sfn.start_execution(stateMachineArn=STATE_MACHINE_ARN, name=scan_id,
                         input=json.dumps({"scan_id": scan_id,
                                           "target": target.to_dict()}))
    return _resp(202, {"scan_id": scan_id, "status": "QUEUED"})
