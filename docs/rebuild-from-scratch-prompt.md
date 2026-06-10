# Rebuild Prompt — Tier2 AI Pentest App (from scratch)

> Paste everything below the line into Claude Code (or another coding agent) to
> rebuild this project from zero. It captures every requirement, decision, and
> feature. Adjust account/region/secrets as needed.

---

## Role & goal

Build a **2-tier, AI-driven penetration-testing app** for **authorized** security
testing. A web frontend takes a target (IP/host, port, endpoint); an AWS backend
(1) generates a **random attacker profile**, (2) uses **Amazon Bedrock + Claude
Opus** to author a tailored **pentest scenario**, then (3) **executes** that
scenario against the authorized target via an **Opus-driven HTTP tool-use loop**,
returning the profile, scenario, and findings.

This is offensive tooling — enforce strict safety controls (below). Only ever run
it against systems the operator is explicitly authorized to test.

## How to work (process)

1. **Brainstorm first.** Before writing code, run a brainstorming/design pass:
   ask clarifying questions one at a time, propose 2–3 approaches with a
   recommendation, present the design in sections, and get approval. (If the
   `superpowers` plugin is available, use its `brainstorming` then `writing-plans`
   then `subagent-driven-development` skills.)
2. Write a **design spec** and an **implementation plan** (TDD, bite-sized tasks,
   exact file paths, complete code, frequent commits) under `docs/`.
3. Implement **test-first** (pytest + moto for backend; `tsc`/`next build` for FE).
4. **Verify** with real commands before claiming done. Commit per task.
5. Pause for explicit approval before any **production deploy**.

## Tech stack

- **Backend:** Python 3.12 Lambdas, AWS CDK v2 (Python), boto3, httpx.
- **AI:** Amazon Bedrock, **Claude Opus** cross-region inference profile
  (`us.anthropic.claude-opus-4-5-20251101-v1:0`, override via env `BEDROCK_OPUS_MODEL`).
- **AWS:** API Gateway (REST), Lambda, **Step Functions (Standard)**, DynamoDB
  (single-table), S3, SSM Parameter Store, VPC + NAT.
- **Frontend:** Next.js (App Router, TypeScript) deployed on **Vercel**.
- **Tests:** pytest, pytest-asyncio, moto.

## Architecture (chosen approach: Step Functions orchestrator)

```
Next.js/Vercel  --POST /scan-->  API Gateway (REST + API key + CORS)
                <-GET /scan/{id}-        |
                                    SubmitScan Lambda (validate, create job, start SFN)
                                          |
   Step Functions (Standard):  ValidateScope -> MakeRoster -> Swarm[Map] -> Report
                                          |                       |
                                  fail-closed scope        N parallel agents
                                          |               (each: random profile ->
                                  DynamoDB (jobs+findings)  Opus scenario -> exec loop)
                                  S3 (markdown reports)          | egress via NAT
                                                                 v  authorized target
```

Async by design: `POST /scan` returns a `scan_id` immediately; the FE polls
`GET /scan/{id}` until a terminal status. (The execution loop is long-running, so
it cannot be synchronous behind API Gateway's ~29s limit.)

## Backend modules (suggested layout)

```
backend/src/common/
  models.py          # Severity, Finding, Target(.from_parts infers https on 443/8443), ScanContext
  scope_guard.py     # SSM allowlist, assert_in_scope (FAIL-CLOSED); host/host:port/CIDR
  bedrock.py         # invoke_opus(text) + converse(tool-use); default model = Opus
  attacker_profile.py# generate() -> random adversary (archetype, skill, motivation, stealth,
                     # aggressiveness, preferred_ttps, toolset, mitre_tactics); to_prose()
  scenario.py        # generate_scenario(profile, target) -> (markdown, engine);
                     # offline-sim template fallback when Bedrock unavailable
  http_client.py     # AuditedClient: rate-limited (semaphore + min interval), verify=False,
                     # logs every request as JSON to stdout (CloudWatch); no-DoS
  store.py           # DynamoDB single-table: create_job/update_job/put_finding/put_agent/get_scan;
                     # float<->Decimal conversion; dedupe findings across agents
backend/src/agents/
  llm_agent.py       # Opus tool-use loop: ENDPOINT DISCOVERY pass (wordlist) -> feed all live
                     # endpoints to Opus -> test every one; tools: http_request(path-only),
                     # report_finding(path,severity,evidence,poc,remediation,attack_method);
                     # caps: <=22 iterations, <=60 requests, body truncate; on_finding callback
backend/src/lambdas/
  submit_scan.py     # POST /scan: validate ip/port/endpoint/authorized/scheme/agents; start SFN
  get_scan.py        # GET /scan/{id}: job meta + agents[] + findings[]
  get_scope.py       # GET /scope: return SSM allowlist {"targets":[...]} for the FE dropdown
  make_roster.py     # SFN: turn agents count (1-8, default 5) into roster list, mark RUNNING
  swarm_agent.py     # SFN Map worker: one agent = profile -> scenario -> exec loop; catches errors
  report.py          # SFN: synthesize markdown -> S3; preserve FAILED/REJECTED status
  mark_failed.py     # SFN Catch target: mark FAILED (don't clobber REJECTED), preserve event
backend/run_local.py # run profile->scenario->loop in-process, no AWS
infra/               # CDK: network_stack, data_stack, compute_stack, orchestration_stack
app.py, cdk.json
frontend/            # Next.js App Router (page.tsx, lib/api.ts, components/*)
scripts/             # build_layer.ps1, set_scope.ps1, register_target.sh/.bat
```

## API contract

- `POST /scan` (header `x-api-key`):
  ```json
  { "ip": "1.2.3.4", "port": 8080, "endpoint": "/login",
    "authorized": true, "scheme": "https (optional)", "agents": 5 }
  ```
  → `202 {"scan_id": "...", "status": "QUEUED"}`. `authorized` MUST be `true`.
- `GET /scan/{id}` (header `x-api-key`) → full job:
  `{ scan_id, status (QUEUED|RUNNING|DONE|FAILED|REJECTED), target{ip,port,endpoint,scheme,url},
     engine, agents:[{index,profile,scenario,engine,error}], scenario, report_url, error,
     findings:[{finding_id,title,severity(lowercase),endpoint,evidence,poc,remediation,attack_method,persona}] }`
- `GET /scope` (header `x-api-key`) → `{"targets": ["1.2.3.4:8080", ...]}`.
- REST API: API key + usage plan; CORS allow the Vercel origin for GET/POST/OPTIONS,
  headers `content-type, x-api-key`.

## Data model (DynamoDB single table)

| Item | pk | sk | attrs |
|------|----|----|-------|
| Job | `SCAN#<id>` | `META` | status, target, profile, scenario, engine, agent_count, report_url, error, created_at |
| Agent | `SCAN#<id>` | `AGENT#<i>` | index, profile, scenario, engine, error |
| Finding | `SCAN#<id>` | `FIND#<fid>` | title, severity, endpoint, evidence, poc, remediation, attack_method, persona |

`GET` = one query on `pk` → assemble job + agents[] + (severity-sorted, deduped) findings[].

## Features (must include)

1. **Random attacker profile** generated BEFORE the scenario, every scan.
2. **Opus-authored scenario** tailored to that profile + target (markdown, MITRE-mapped),
   with a clearly-labelled **offline-sim fallback** if Bedrock is unreachable.
3. **Opus-driven execution loop** that actually probes the target and reports findings.
4. **Full-surface scanning:** deterministic endpoint-discovery pass over a ~48-path
   wordlist (+ seed); feed all live endpoints (status != 404) to Opus; test each.
5. **HTTP and HTTPS targets:** infer scheme from port (443/8443 → https), optional
   `scheme` override.
6. **Permitted-target dropdown:** `GET /scope` powers a FE dropdown (with manual
   fallback) so users pick allowlisted targets instead of typing them.
7. **Multi-agent swarm:** caller-specified `agents` (1–8, default 5); fan out via
   Step Functions `Map` (maxConcurrency 3); each agent its own persona + scenario;
   findings merged and **deduped** across agents under one `scan_id`.

## Safety controls (non-negotiable)

- **Authorization gate:** reject unless request `authorized == true`.
- **Fail-closed scope allowlist** in SSM (`/tier2/scope-allowlist`): every scan
  calls `assert_in_scope(target)`; empty/unset list rejects everything;
  out-of-scope → job `REJECTED`. Re-check inside the executor.
- **API key** on the public API (usage plan + throttle).
- **Audited, rate-limited HTTP client** (semaphore + min interval; logs every
  outbound request to CloudWatch).
- **Hard caps:** ≤22 reasoning turns, ≤60 requests per agent, ≤8 agents,
  Map maxConcurrency 3, response-body truncation.
- **No SSRF:** the HTTP tool takes a PATH only, always joined to the one
  authorized host. **No DoS / no flooding** (prompt-forbidden + rate-limited).
- **Least-privilege IAM** per Lambda; executor runs in VPC behind NAT with an
  egress security group; Bedrock IAM must grant **both** `bedrock:InvokeModel`
  and `bedrock:Converse`.

## Error handling

- Bad input / `authorized!=true` → 400 (nothing queued). Bad/missing key → 403.
- Bedrock unavailable → offline-sim scenario, pipeline still completes; `engine`
  records `bedrock-opus` vs `offline-sim`.
- Per-state SFN `Retry` (exp backoff) + `Catch` → `MarkFailed`; `Report` still runs
  on the failure path; partial findings retained; FE never hangs.
- Frontend polls ~2–15s, retries transient poll failures, stops on terminal status.

## Frontend (Next.js on Vercel)

- Form: target dropdown (from `GET /scope`) + manual ip/port/endpoint, **"agents 1–8"**
  input, and a required **"I am authorized"** checkbox (submit disabled until checked).
- After submit, poll `GET /scan/{id}`; render: status badge, **"Attacker swarm (N)"**
  (each persona card + collapsible scenario), and a severity-sorted findings list;
  show the S3 report link on DONE.
- Simple API-key mode (key in `NEXT_PUBLIC_API_KEY`); design so a server-side proxy
  route can hide the key later without backend changes.

## Testing

- pytest + moto: profile fields/seeded-RNG reproducibility; scope guard
  (in/out/empty/CIDR); scenario offline fallback; llm_agent loop via a mock
  converse_fn (caps, scope re-check, finding recording, discovery wordlist);
  store (float↔Decimal, agents, dedupe); submit_scan validation (authorized, port,
  ip, endpoint, scheme, agents); SFN state handlers (validate, make_roster clamp,
  swarm_agent stream). `cdk synth` smoke. Frontend `tsc --noEmit` + `next build`.

## Deployment

1. `pip install -r backend/requirements.txt`; build the Lambda layer
   (`pip install -r backend/requirements-lambda.txt -t build/layer/python`).
2. `npx cdk bootstrap`; `npx cdk deploy --all` → outputs API URL + API key.
3. Enable Bedrock Opus model access in the region (console).
4. Set scope: `scripts/set_scope.ps1 -Scope "<host:port>"` (fail-closed until set);
   add targets incrementally with `scripts/register_target.sh|.bat <host> <port>`.
5. Frontend: set `NEXT_PUBLIC_API_BASE` + `NEXT_PUBLIC_API_KEY` on Vercel; deploy.
   Add the Vercel origin to API Gateway CORS.

## Reference

An earlier AWS pentest-swarm project demonstrates the proven patterns to adapt
(scope guard, audited client, Bedrock converse wrapper, personas, CDK stacks,
Step Functions Map fan-out). Reuse/adapt those rather than reinventing.

## Acceptance criteria

- End-to-end: submit a scan against an allowlisted target → random profile(s) +
  Opus scenario(s) generated → live requests sent (visible in CloudWatch) →
  findings returned → markdown report in S3. Out-of-scope target → `REJECTED`.
  Multi-agent run shows N distinct personas under one `scan_id` with deduped
  findings. HTTP and HTTPS targets both work. No control bypasses the scope/auth
  gates. All tests green; `cdk synth`, `tsc`, `next build` succeed.
```
