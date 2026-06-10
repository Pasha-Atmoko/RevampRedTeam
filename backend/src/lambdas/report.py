# backend/src/lambdas/report.py
"""SFN state: synthesize a markdown report to S3 and mark the job DONE."""
from __future__ import annotations

import os

import boto3

from common import store

REPORT_BUCKET = os.environ.get("REPORT_BUCKET", "")
_s3 = boto3.client("s3")


def _markdown(job: dict) -> str:
    t = job["target"]
    agents = job.get("agents") or []
    lines = [f"# Tier2 Pentest Report - {t['url']}{t['endpoint']}", "",
             f"Agents: {len(agents) or 1}  |  Findings (deduped): "
             f"{len(job.get('findings', []))}", ""]
    if agents:
        lines += ["## Attacker Swarm"]
        for a in agents:
            p = a.get("profile") or {}
            tag = " (failed)" if a.get("error") else ""
            lines.append(f"- **#{a.get('index')}** {p.get('archetype', 'agent')} "
                         f"({p.get('alias', '?')}) — {p.get('skill_level', '')}{tag}")
        lines += ["", "## Scenario (agent #0)",
                  (agents[0].get("scenario") or "(none)"), ""]
    else:
        lines += ["## Scenario", job.get("scenario") or "(none)", ""]
    lines += ["## Findings"]
    for f in job.get("findings", []):
        lines += [f"### [{f['severity'].upper()}] {f['title']}",
                  f"- attack_method: {f.get('attack_method','')}",
                  f"- evidence: {f.get('evidence','')}",
                  f"- poc: {f.get('poc','')}",
                  f"- remediation: {f.get('remediation','')}", ""]
    return "\n".join(lines)


def handler(event, context):
    scan_id = event["scan_id"]
    job = store.get_scan(scan_id)
    report_url = None
    if REPORT_BUCKET and job:
        key = f"reports/{scan_id}.md"
        _s3.put_object(Bucket=REPORT_BUCKET, Key=key,
                       Body=_markdown(job).encode("utf-8"),
                       ContentType="text/markdown")
        report_url = f"s3://{REPORT_BUCKET}/{key}"
    current = job.get("status") if job else None
    final = current if current in ("FAILED", "REJECTED") else "DONE"
    store.update_job(scan_id, status=final, report_url=report_url)
    return {**event, "status": final, "report_url": report_url}
