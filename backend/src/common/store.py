# backend/src/common/store.py
"""DynamoDB single-table persistence for scan jobs and findings.

Layout:
  job item     pk=SCAN#<id> sk=META   (status, target, profile, scenario, ...)
  finding item pk=SCAN#<id> sk=FIND#<finding_id>
"""
from __future__ import annotations

import os
import time
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Key

TABLE = os.environ.get("SCANS_TABLE", "tier2-scans")


@lru_cache(maxsize=1)
def _table():
    return boto3.resource("dynamodb").Table(TABLE)


def create_job(scan_id: str, target: dict) -> None:
    _table().put_item(Item={
        "pk": f"SCAN#{scan_id}", "sk": "META", "scan_id": scan_id,
        "status": "QUEUED", "target": target, "profile": None, "scenario": None,
        "engine": None, "report_url": None, "error": None,
        "created_at": int(time.time())})


def update_job(scan_id: str, **fields) -> None:
    if not fields:
        return
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": v for k, v in fields.items()}
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
    _table().update_item(Key={"pk": f"SCAN#{scan_id}", "sk": "META"},
                         UpdateExpression=expr,
                         ExpressionAttributeNames=names,
                         ExpressionAttributeValues=values)


def put_finding(scan_id: str, finding: dict) -> None:
    item = {"pk": f"SCAN#{scan_id}", "sk": f"FIND#{finding['finding_id']}", **finding}
    _table().put_item(Item=item)


def get_scan(scan_id: str) -> dict | None:
    resp = _table().query(KeyConditionExpression=Key("pk").eq(f"SCAN#{scan_id}"))
    items = resp.get("Items", [])
    meta = next((i for i in items if i["sk"] == "META"), None)
    if meta is None:
        return None
    findings = [_finding_view(i) for i in items if i["sk"].startswith("FIND#")]
    findings.sort(key=lambda f: _SEV_RANK.get(f["severity"], 0), reverse=True)
    out = {k: v for k, v in meta.items() if k not in ("pk", "sk")}
    out["findings"] = findings
    return out


_SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _finding_view(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("pk", "sk")}
