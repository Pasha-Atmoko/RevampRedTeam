# backend/src/lambdas/mark_failed.py
"""SFN Catch target: record a terminal failure so the FE never hangs."""
from __future__ import annotations

from common import store


def handler(event, context):
    scan_id = event.get("scan_id")
    err = event.get("error", {})
    cause = err.get("Cause") if isinstance(err, dict) else str(err)
    if scan_id:
        # Do not clobber a REJECTED status set by ValidateScope.
        job = store.get_scan(scan_id)
        if job and job.get("status") != "REJECTED":
            store.update_job(scan_id, status="FAILED", error=str(cause)[:1000])
    return {"status": "FAILED"}
