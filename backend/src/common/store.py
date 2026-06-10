# backend/src/common/store.py
"""DynamoDB single-table persistence for scan jobs and findings.

Layout:
  job item     pk=SCAN#<id> sk=META   (status, target, profile, scenario, ...)
  finding item pk=SCAN#<id> sk=FIND#<finding_id>

DynamoDB does not accept Python ``float`` (e.g. the attacker profile's
``stealth``/``aggressiveness``) — it requires ``Decimal``. ``_to_dynamo``
converts floats to Decimal on the way in, and ``_from_dynamo`` converts Decimals
back to int/float on the way out so the API returns plain JSON numbers.
"""
from __future__ import annotations

import os
import time
from decimal import Decimal
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Key

TABLE = os.environ.get("SCANS_TABLE", "tier2-scans")


@lru_cache(maxsize=1)
def _table():
    return boto3.resource("dynamodb").Table(TABLE)


def _to_dynamo(obj):
    """Recursively convert floats to Decimal for DynamoDB writes."""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: _to_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_dynamo(v) for v in obj]
    return obj


def _from_dynamo(obj):
    """Recursively convert DynamoDB Decimals back to int/float for JSON."""
    if isinstance(obj, Decimal):
        return int(obj) if obj == obj.to_integral_value() else float(obj)
    if isinstance(obj, dict):
        return {k: _from_dynamo(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_from_dynamo(v) for v in obj]
    return obj


def create_job(scan_id: str, target: dict) -> None:
    _table().put_item(Item=_to_dynamo({
        "pk": f"SCAN#{scan_id}", "sk": "META", "scan_id": scan_id,
        "status": "QUEUED", "target": target, "profile": None, "scenario": None,
        "engine": None, "report_url": None, "error": None,
        "created_at": int(time.time())}))


def update_job(scan_id: str, **fields) -> None:
    if not fields:
        return
    names = {f"#{k}": k for k in fields}
    values = {f":{k}": _to_dynamo(v) for k, v in fields.items()}
    expr = "SET " + ", ".join(f"#{k} = :{k}" for k in fields)
    _table().update_item(Key={"pk": f"SCAN#{scan_id}", "sk": "META"},
                         UpdateExpression=expr,
                         ExpressionAttributeNames=names,
                         ExpressionAttributeValues=values)


def put_finding(scan_id: str, finding: dict) -> None:
    item = {"pk": f"SCAN#{scan_id}", "sk": f"FIND#{finding['finding_id']}", **finding}
    _table().put_item(Item=_to_dynamo(item))


def put_agent(scan_id: str, index: int, profile: dict, scenario: str,
              engine: str, error: str | None = None) -> None:
    """Record one swarm agent's persona + scenario under the scan."""
    _table().put_item(Item=_to_dynamo({
        "pk": f"SCAN#{scan_id}", "sk": f"AGENT#{int(index):02d}", "index": int(index),
        "profile": profile, "scenario": scenario, "engine": engine, "error": error}))


def get_scan(scan_id: str) -> dict | None:
    resp = _table().query(KeyConditionExpression=Key("pk").eq(f"SCAN#{scan_id}"))
    items = resp.get("Items", [])
    meta = next((i for i in items if i["sk"] == "META"), None)
    if meta is None:
        return None
    findings = [_finding_view(i) for i in items if i["sk"].startswith("FIND#")]
    findings.sort(key=lambda f: _SEV_RANK.get(f["severity"], 0), reverse=True)
    findings = _dedupe(findings)
    agents = [_finding_view(i) for i in items if i["sk"].startswith("AGENT#")]
    agents.sort(key=lambda a: a.get("index", 0))
    out = {k: v for k, v in meta.items() if k not in ("pk", "sk")}
    out["findings"] = findings
    out["agents"] = agents
    return _from_dynamo(out)


def _dedupe(findings: list[dict]) -> list[dict]:
    """Collapse identical findings reported by multiple swarm agents."""
    seen, out = set(), []
    for f in findings:
        key = (str(f.get("title", "")).strip().lower(), f.get("endpoint"),
               f.get("severity"))
        if key in seen:
            continue
        seen.add(key)
        out.append(f)
    return out


_SEV_RANK = {"critical": 4, "high": 3, "medium": 2, "low": 1, "info": 0}


def _finding_view(item: dict) -> dict:
    return {k: v for k, v in item.items() if k not in ("pk", "sk")}
