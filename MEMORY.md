# Tier2 — Session Memory / Project Log

> A human-readable record of what was built in this project and how to resume.
> Last updated: 2026-06-10.

## What this project is

A **2-tier, AI-driven penetration-testing app** for **authorized** testing:
1. A **Next.js frontend (on Vercel)** takes a target (IP/host, port, endpoint).
2. An **AWS backend** generates a **random attacker profile**, uses **Bedrock +
   Claude Opus** to author a tailored **pentest scenario**, then **executes** it
   against the authorized target via an **Opus-driven HTTP tool-use loop**, and
   returns the profile, scenario, and findings.

Built via: brainstorming → design spec → implementation plan → subagent-driven
TDD build → deploy → iterative feature additions.

## Live resources

| Thing | Value |
|------|-------|
| GitHub repo | https://github.com/GreenLovePie/RevampRedTeam (branch `main`) |
| Frontend (Vercel) | https://revamp-red-team.vercel.app  (Vercel project `revamp-red-team`, acct `greendev2008-7727`) |
| API base (AWS) | https://r578qyt8l2.execute-api.us-east-1.amazonaws.com/prod/ |
| API key (demo) | `tier2-demo-key-7h3x9q2`  ⚠️ public in repo — rotate for real use |
| AWS account / region | `749206544732` / `us-east-1` |
| DynamoDB table | `Tier2-Data-Scans941C181C-UZ6VJIURR8AY` |
| S3 reports bucket | `tier2-data-reports65402a0a-mnmnk70lmhpw` |
| Attacker egress IP (NAT) | **`34.196.189.227`** — allowlist this on targets that IP-filter |
| Scope allowlist (SSM) | `/tier2/scope-allowlist` → currently `54.84.126.64:80`, `api.cashlo.id:443` |

## Architecture

`API Gateway (REST + API key + CORS)` → `SubmitScan λ` → **Step Functions (Standard)**:
`ValidateScope → MakeRoster → Swarm[Map, maxConcurrency 3] → Report` →
DynamoDB (single table) + S3 (markdown reports). Frontend polls `GET /scan/{id}`.
Opus model: `us.anthropic.claude-opus-4-5-20251101-v1:0`.

## API quick reference

- `POST /scan` (hdr `x-api-key`): `{ip, port, endpoint, authorized:true, scheme?, agents?}` → `202 {scan_id, status:"QUEUED"}`
- `GET /scan/{id}` (hdr `x-api-key`): full job → status, target, agents[], scenario, findings[], report_url, error
- `GET /scope` (hdr `x-api-key`): `{"targets":[...]}` (the allowlist)
- Statuses: `QUEUED | RUNNING | DONE | FAILED | REJECTED`

## What was built (chronological)

1. **Initial build** — full app via brainstorm → spec → plan → subagent-driven TDD
   (24 tests). Deployed AWS (4 CDK stacks) + Vercel.
2. **Bug fix (live):** DynamoDB rejects Python `float` → added float↔Decimal in `store.py`.
3. **Multi-endpoint scanning:** deterministic wordlist discovery (~48 paths) →
   Opus tests every live endpoint; caps raised; `report_finding` gained `path`.
4. **Target dropdown:** new `GET /scope` + FE dropdown (manual fallback).
5. **HTTPS targets:** `Target.from_parts` infers `https` for 443/8443 (+ optional
   `scheme` override). Verified live against `api.cashlo.id:443`.
6. **Diagnosis "defender sees no attack":** CloudWatch showed ~55 requests to
   `54.84.126.64:80` all returning blanket **403** — the target's nginx edge is
   **denylisting our NAT IP `34.196.189.227`** (other IPs get 404). Likely the
   defender auto-blocked us after the first detected attack. Fix = allowlist that IP.
7. **Multi-agent swarm (built, NOT yet deployed):** `agents` 1–8 (default 5);
   Step Functions `Map`; each agent = own random persona + own Opus scenario;
   findings merged/deduped under one `scan_id`; FE shows "Attacker swarm (N)".
   37 tests pass; `cdk synth`, `tsc`, `next build` all green; committed + pushed.

## Current state

- **Deployed & live:** single/multi-endpoint scanning, HTTP+HTTPS, target dropdown.
- **Built but NOT deployed yet:** the **multi-agent swarm** (commit on `main`).
  To ship it: deploy backend + frontend (see below).

## Key decisions

- Generate **and execute** (not scenario-only); engine = **Opus-driven loop**.
- **AWS**, **fresh standalone CDK**, **Approach A = Step Functions Standard**.
- Frontend = **Next.js on Vercel**, simple API-key mode.
- Swarm: caller-specified **1–8** agents; each its **own profile + scenario**.
- IP randomization intentionally **skipped** (agents share the NAT IP).

## Open items / TODO

- [ ] **Deploy the swarm** (BE + FE) — built, awaiting go-ahead.
- [ ] Allowlist `34.196.189.227` on `54.84.126.64` so the defender receives attacks again.
- [ ] Rotate secrets: Vercel token + demo API key (both exposed in chat/repo).
- [ ] Optional: WAF detect/tamper, block-aware budget control, adversarial verifier,
      true IP rotation (proxy pool), FE scheme toggle, secure API-key proxy route,
      tighten egress security group.
- [ ] **Cost:** NAT gateway bills ~$32/mo — tear down when done.

## How to resume (commands)

```powershell
# from C:\Users\green\OneDrive\Desktop\Tier2
# backend tests
cd backend; .\.venv\Scripts\python -m pytest -q; cd ..

# deploy backend (asks nothing; only on your go-ahead)
$env:AWS_REGION="us-east-1"
npx cdk deploy --all --require-approval never --app "backend\.venv\Scripts\python.exe app.py"

# deploy frontend (needs a Vercel token)
cd frontend; npx vercel deploy --prod --yes --scope greendev2008gmailcoms-projects; cd ..

# manage authorized targets
bash scripts/register_target.sh <host> <port>      # add (Linux/Git Bash)
scripts\register_target.bat <host> <port>          # add (Windows cmd)
bash scripts/register_target.sh --list             # show allowlist

# run a scan via API
curl -X POST "https://r578qyt8l2.execute-api.us-east-1.amazonaws.com/prod/scan" `
  -H "x-api-key: tier2-demo-key-7h3x9q2" -H "content-type: application/json" `
  -d '{"ip":"54.84.126.64","port":80,"endpoint":"/login","authorized":true,"agents":3}'

# TEARDOWN (stop AWS costs)
npx cdk destroy --all --app "backend\.venv\Scripts\python.exe app.py"
```

## Docs in this repo

- `docs/superpowers/specs/2026-06-10-tier2-pentest-app-design.md` — design spec
- `docs/superpowers/plans/2026-06-10-tier2-pentest-app.md` — implementation plan (TDD tasks)
- `docs/frontend-integration-prompt.md` — spec for a frontend team to integrate
- `docs/rebuild-from-scratch-prompt.md` — paste-ready prompt to rebuild from zero
- `scripts/README.md` — scope-management + layer scripts
- `README.md` — setup / deploy / safety

## Safety model (always on)

Authorization gate (`authorized:true`) · fail-closed SSM scope allowlist ·
API key · audited rate-limited HTTP client · caps (≤22 turns / ≤60 req per agent,
≤8 agents, Map concurrency 3) · path-only requests (no SSRF) · no DoS ·
least-privilege IAM · executor in VPC behind NAT. Only test authorized targets.
