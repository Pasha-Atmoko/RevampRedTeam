# Prompt: Build a Frontend for the Tier2 AI-Pentest Backend

> Paste this whole document to your frontend developer (or your AI coding agent).
> It is the **authoritative contract**. Build to exactly what is described here —
> do **not** add domains, vector menus, fraud flows, sync reports, callbacks, or
> ticket fields. Those do not exist in this backend.

---

## 1. Mission

Build a web frontend that lets an authorized operator launch an AI-driven
penetration test against a single target, watch it run, and read the results.

The backend:
1. takes a target (IP/host, port, endpoint),
2. generates a **random attacker profile**,
3. has **Claude Opus** author a tailored pentest **scenario**,
4. runs an **adaptive Opus tool-use loop** that probes the target and records
   **findings**,
5. writes a markdown report to S3.

The work is **asynchronous**: you submit a scan, get a `scan_id`, then **poll**
until it reaches a terminal status. The UI renders the profile, the scenario,
and the findings as they arrive.

## 2. Hard constraints — do NOT assume these (they are not supported)

- ❌ No `domain` concept (no `attack`/`fraud`/`redteam`). Single capability only.
- ❌ No selectable "vectors"/"scenarios"/"attack_type". Techniques are chosen at
  runtime by Opus; there is no catalog endpoint and nothing to pick from.
- ❌ No **fraud** capability of any kind.
- ❌ No **synchronous** result. `POST` returns a `scan_id`; you must poll.
- ❌ No `ok: true/false` envelope on responses.
- ❌ No webhooks/callbacks. The backend never calls you. Pull/poll only.
- ❌ No ticket correlation (`mapped_ticket_id`/`linked_ticket_ids`/`correlation_id`).
  The only id is `scan_id`. Use it as your correlation key.
- ❌ No `options`/`max_attempts`/`max_steps`/`safe_mode` inputs. Limits are fixed
  server-side and not configurable.
- ❌ No `summary`/`steps`/`defender_result` objects in the response.
- ❌ HTTPS targets are **not** supported yet (backend builds `http://ip:port`).
- ❌ Severities are **lowercase** (`critical|high|medium|low|info`), not `HIGH`.

## 3. Configuration

| Setting | Value |
|---|---|
| Base URL | `https://r578qyt8l2.execute-api.us-east-1.amazonaws.com/prod` |
| Auth header | `x-api-key: <key>` (required on every request) |
| Demo key | `tier2-demo-key-7h3x9q2` *(public demo key — will be rotated; read it from an env var, never hardcode)* |

**Security:** the API key must NOT ship in browser-visible code in production.
Put it behind a server-side proxy (e.g. a Next.js route handler / serverless
function) that injects `x-api-key` and forwards to the base URL. The browser
calls your proxy; the proxy calls the backend.

## 4. API contract

### 4.1 Launch a scan
```
POST {BASE}/scan
Headers: Content-Type: application/json, x-api-key: <key>
Body:
{
  "ip": "54.84.126.64",   // IPv4 or hostname (string, required)
  "port": 80,              // integer 1–65535 (required)
  "endpoint": "/login",    // path beginning with "/" (required; default "/login")
  "authorized": true       // MUST be exactly true, or 400
}
```
**Success → HTTP 202**
```json
{ "scan_id": "4bd3b9bc40634d13ab67a56eec4ce68f", "status": "QUEUED" }
```
Map `run_id := scan_id` if your UI uses "run".

### 4.2 Poll a scan
```
GET {BASE}/scan/{scan_id}
Headers: x-api-key: <key>
```
**Response (one object containing everything):**
```json
{
  "scan_id": "4bd3b9bc...",
  "status": "RUNNING",                 // QUEUED | RUNNING | DONE | FAILED | REJECTED
  "engine": "bedrock-opus",            // or "offline-sim" if Bedrock was unavailable; null early
  "target": { "ip": "54.84.126.64", "port": 80, "endpoint": "/login", "url": "http://54.84.126.64:80" },
  "profile": {                          // null until generated
    "alias": "frost_magpie05",
    "archetype": "The Impersonator",
    "emoji": "🎭",
    "skill_level": "Advanced",
    "skill_desc": "writes custom tooling, chains novel bugs, careful about detection",
    "motivation": "Hacktivism (defacement / leak to make a statement)",
    "origin": "Eastern Europe",
    "crew_size": "State-sponsored team",
    "stealth": 0.88,                    // float 0..1
    "aggressiveness": 0.16,             // float 0..1
    "preferred_ttps": ["CORS misconfiguration abuse", "default / guessable credentials"],
    "toolset": ["gobuster", "Hydra", "sqlmap"],
    "mitre_tactics": ["TA0043 Reconnaissance", "TA0007 Discovery"]
  },
  "scenario": "# Penetration Test Scenario ... (GitHub-flavored markdown)",  // null until generated
  "report_url": "s3://tier2-data-reports.../reports/<scan_id>.md",           // null until DONE/FAILED
  "error": null,                        // string on FAILED/REJECTED
  "created_at": 1781094220,             // unix seconds (int)
  "findings": [                         // grows while RUNNING
    {
      "finding_id": "1e4999...",
      "title": "Username Enumeration via Differential Error Messages",
      "severity": "medium",            // critical|high|medium|low|info  (LOWERCASE)
      "endpoint": "http://54.84.126.64:80/login",
      "evidence": "admin -> 'account blocked' (403); unknown -> 'invalid credentials' (401)",
      "poc": "curl -X POST http://54.84.126.64/login -d '{\"username\":\"admin\",...}'",
      "remediation": "Return generic auth errors; constant-time responses.",
      "attack_method": "differential error-message probing",
      "persona": "The Impersonator (frost_magpie05)"
    }
  ]
}
```

### 4.3 Statuses
| Status | Meaning | Terminal? |
|---|---|---|
| `QUEUED` | accepted, workflow starting | no |
| `RUNNING` | profile/scenario done; loop probing target; findings streaming | no |
| `DONE` | finished; `report_url` set | yes |
| `FAILED` | error mid-run; `error` set; partial findings kept; report still written | yes |
| `REJECTED` | target not in the authorized scope allowlist; `error` set | yes |

**Polling:** every **~15s**; stop on any terminal status. Typical total run ≈ 1–3 min.

### 4.4 Errors
| Case | HTTP | Body |
|---|---|---|
| Bad/missing API key | `403` | `{"message":"Forbidden"}` (API Gateway format) |
| `authorized` not true | `400` | `{"error":"Field 'authorized' must be true (you must confirm authorization)."}` |
| Bad port / ip / endpoint | `400` | `{"error":"Field '...' ..."}` |
| Malformed JSON | `400` | `{"error":"Body must be valid JSON."}` |
| Unknown scan id | `404` | `{"error":"scan not found"}` |
| Out-of-scope / runtime failure | — | not a POST error; surfaces via polling as `REJECTED`/`FAILED` with `error` |

## 5. TypeScript types (use these verbatim)
```ts
export type ScanStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "REJECTED";
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface LaunchRequest {
  ip: string; port: number; endpoint: string; authorized: true;
}
export interface LaunchResponse { scan_id: string; status: "QUEUED"; }

export interface Profile {
  alias: string; archetype: string; emoji?: string;
  skill_level: string; skill_desc?: string; motivation: string;
  origin: string; crew_size: string; stealth: number; aggressiveness: number;
  preferred_ttps: string[]; toolset: string[]; mitre_tactics: string[];
}
export interface Finding {
  finding_id: string; title: string; severity: Severity; endpoint: string;
  evidence: string; poc?: string; remediation?: string;
  attack_method?: string; persona?: string;
}
export interface Scan {
  scan_id: string; status: ScanStatus; engine: string | null;
  target: { ip: string; port: number; endpoint: string; url: string };
  profile: Profile | null; scenario: string | null;
  report_url: string | null; error: string | null; created_at: number;
  findings: Finding[];
}
```

## 6. User stories

- **US1 — Launch:** As an operator, I enter a target IP/host, port, and endpoint,
  confirm I'm authorized, and start a scan, so the backend can begin.
  - The "Launch" button is disabled until the authorization checkbox is ticked
    and ip/port/endpoint are valid.
- **US2 — Authorization gate:** As a responsible operator, I must explicitly
  confirm authorization before any scan, so we never test unauthorized systems.
- **US3 — Live progress:** As an operator, after launching I see the status
  (`QUEUED→RUNNING→DONE`) update automatically without refreshing.
- **US4 — See the adversary:** As an operator, once generated I see the random
  attacker profile (who is "attacking" and how).
- **US5 — Read the plan:** As an operator, I read the Opus-authored scenario
  (rendered markdown) tailored to that profile and target.
- **US6 — Review findings:** As an operator, I see findings appear as they're
  reported, sorted by severity, each with evidence, PoC, and remediation.
- **US7 — Get the report:** On `DONE`, I see the `report_url` (S3) for the full
  markdown report.
- **US8 — Handle rejection:** If the target isn't authorized (`REJECTED`), I see
  a clear scope-error message and no findings.
- **US9 — Handle failure:** On `FAILED`, I see the error and any partial findings.
- **US10 — Resilient polling:** If a poll request blips, the UI keeps the
  `scan_id` and resumes polling rather than losing the run.

## 7. Screens / UX

1. **Launch form**
   - Fields: `IP / host` (text), `Port` (number, default 8080 or 80), `Endpoint`
     (text, default `/login`), `I confirm I am authorized to test this target`
     (checkbox).
   - Client-side validation mirroring the API (port 1–65535, endpoint starts `/`).
   - Submit → `POST /scan` → store `scan_id` → switch to Run view.
2. **Run / progress view**
   - Status badge with color (QUEUED grey, RUNNING blue/pulsing, DONE green,
     FAILED red, REJECTED amber). Show `engine` and `created_at`.
   - Begin polling `GET /scan/{id}` every 15s; stop on terminal.
3. **Results (progressive)**
   - **Profile card** (alias, archetype+emoji, skill, motivation, origin/crew,
     stealth/aggressiveness, TTPs, toolset, MITRE).
   - **Scenario** — render the markdown string.
   - **Findings list** — sorted by severity (critical→info), severity chip with
     color, title, `attack_method`, `endpoint`, `evidence` (mono), `poc` (mono),
     `remediation`. Show a count.
   - **Report link** on DONE.
4. **States:** empty (no scan yet), loading, REJECTED banner, FAILED banner,
   connection-lost (poll retry) banner.

## 8. Behavior details (must implement)

- Map `run_id` ↔ `scan_id` if your terminology differs.
- Severity is lowercase — uppercase only for display if you want.
- Findings array grows across polls; re-render idempotently (key by `finding_id`).
- Poll every ~15s; backoff/retry on transient errors; never poll after terminal.
- All requests carry `x-api-key` (via your server-side proxy).
- Do not send `run_id`, `domain`, `vector_id`, `options`, or `callback_url` — the
  backend ignores them; `authorized:true` is mandatory.

## 9. Safety copy (show to users)

> This launches a real, bounded penetration test against the target you specify.
> Only run it against systems you are explicitly authorized to test. Targets are
> restricted to an allowlist on the backend; unauthorized targets are rejected.
> Runs are rate-limited and capped (no denial-of-service).

## 10. Acceptance criteria

- [ ] Launch form blocks submit until authorized + valid inputs.
- [ ] `POST /scan` succeeds and the UI transitions to a polling Run view.
- [ ] Status updates QUEUED→RUNNING→DONE automatically.
- [ ] Profile card, scenario markdown, and findings all render from the poll
      payload (no separate endpoints used).
- [ ] Findings sorted by severity with evidence/poc/remediation visible.
- [ ] REJECTED and FAILED render distinct, clear states with `error`.
- [ ] No use of domains/vectors/fraud/callbacks/tickets/options anywhere.
- [ ] API key is never exposed in client bundle (proxy used).

## 11. Reference curl

```bash
# Launch
curl -X POST "https://r578qyt8l2.execute-api.us-east-1.amazonaws.com/prod/scan" \
  -H "Content-Type: application/json" -H "x-api-key: tier2-demo-key-7h3x9q2" \
  -d '{"ip":"54.84.126.64","port":80,"endpoint":"/login","authorized":true}'
# -> 202 {"scan_id":"<id>","status":"QUEUED"}

# Poll
curl "https://r578qyt8l2.execute-api.us-east-1.amazonaws.com/prod/scan/<id>" \
  -H "x-api-key: tier2-demo-key-7h3x9q2"
# -> {"status":"RUNNING|DONE|FAILED|REJECTED","profile":{...},"scenario":"...","findings":[...]}
```

## 12. Notes for the integrator

- To test against your own target, that target's `host:port` must be added to the
  backend scope allowlist (SSM `/tier2/scope-allowlist`) by the backend owner, and
  it must be reachable over **HTTP** (HTTPS not yet supported).
- A reference frontend that already implements this contract exists at
  `https://revamp-red-team.vercel.app` (repo: `GreenLovePie/RevampRedTeam`,
  `frontend/`) — use it as a working example.
```
