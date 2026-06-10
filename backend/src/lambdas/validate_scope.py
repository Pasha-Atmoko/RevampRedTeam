# backend/src/lambdas/validate_scope.py
"""SFN state: fail-closed scope check. Marks job REJECTED and raises if out of scope."""
from __future__ import annotations

from common import store
from common.scope_guard import assert_in_scope, ScopeError, _load_allowlist


def _scope():
    return _load_allowlist()


def handler(event, context):
    scan_id = event["scan_id"]
    target = event["target"]
    try:
        assert_in_scope(target["url"], allowlist=_scope())
    except ScopeError as exc:
        store.update_job(scan_id, status="REJECTED", error=str(exc))
        raise
    return {**event, "in_scope": True}
