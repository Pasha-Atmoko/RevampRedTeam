# Tier2 Attacker Backend — Frontend Build Spec (v2)

> **For any frontend channel building against this backend.** This is the
> authoritative contract. Build to exactly what is here. It supersedes the
> earlier `frontend-integration-prompt.md` and adds the **`GET /scope`** target
> list and **HTTPS/scheme** support.
>
> Status as of 2026-06-10: backend is deployed and live.

---

## 1. What this backend does

An operator submits a single authorized target (host, port, endpoint). The
backend:
1. generates a **random attacker profile**,
2. has **Claude Opus** author a tailored pentest **scenario**,
3. runs a **discovery pass** (probes a wordlist of common paths) then an
   **adaptive Opus tool-use loop** that tests **all discovered endpoints** and
   records **findings**,
4. writes a markdown report to S3.

It is **asynchronous**: submit → get `scan_id` → **poll** until terminal. The UI
renders the profile, the scenario, and findings as they arrive.

## 2. Hard constraints — NOT supported (do not build these)

- ❌ No `domain` (`attack`/`fraud`/`redteam`) — single capability.
- ❌ No selectable vectors/scenarios/`attack_type` — techniques chosen at runtime.
- ❌ No **fraud** flow.
- ❌ No **synchronous** result, no `ok` envelope.
- ❌ No webhooks/callbacks — pull/poll only.
- ❌ No ticket correlation — the only id is `scan_id`.
- ❌ No `options`/`max_attempts`/`max_steps`/`safe_mode` inputs (limits fixed server-side).
- ❌ No `summary`/`steps`/`defender_result` objects.

## 3. Config & auth

| Setting | Value |
|---|---|
| Base URL | `https://r578qyt8l2.execute-api.us-east-1.amazonaws.com/prod` |
| Auth header | `x-api-key: <key>` (required on every request) |
| Demo key | `tier2-demo-key-7h3x9q2` *(public demo key; will be rotated — read from env, never hardcode)* |

**Security:** do not ship the key in browser code in production. Put it behind a
server-side proxy (Next.js route handler / serverless fn) that injects
`x-api-key`. Browser → your proxy → backend.

## 4. Endpoints

### 4.1 `GET /scope` — list permitted targets (for a dropdown)
```
GET {BASE}/scope        Headers: x-api-key
-> 200 { "targets": ["54.84.126.64:80", "api.cashlo.id:443", "10.0.0.0/24"] }
```
- Entries are `host:port`, bare `host`, or CIDR (`x.x.x.x/n`).
- Use this to populate a target picker so the operator doesn't type by hand.
- CIDR entries are not directly launchable (no single host:port) — show them
  disabled or as manual-only.
- Reflects the live server-side allowlist; refetch on load.

### 4.2 `POST /scan` — launch
```
POST {BASE}/scan    Headers: Content-Type: application/json, x-api-key
Body:
{
  "ip": "api.cashlo.id",   // IPv4 or hostname (required)
  "port": 443,              // integer 1–65535 (required)
  "endpoint": "/login",     // path starting "/" (required; default "/login")
  "scheme": "https",        // OPTIONAL "http" | "https". If omitted, inferred:
                            //   port 443/8443 -> https, else http
  "authorized": true        // MUST be exactly true, else 400
}
-> 202 { "scan_id": "4bd3b9bc...", "status": "QUEUED" }
```
Map `run_id := scan_id` if your UI uses "run".

### 4.3 `GET /scan/{id}` — poll status + results
```
GET {BASE}/scan/{scan_id}   Headers: x-api-key
```
```json
{
  "scan_id": "4bd3b9bc...",
  "status": "RUNNING",                 // QUEUED|RUNNING|DONE|FAILED|REJECTED
  "engine": "bedrock-opus",            // or "offline-sim"; null early
  "target": { "ip": "api.cashlo.id", "port": 443, "endpoint": "/login",
              "scheme": "https", "url": "https://api.cashlo.id:443" },
  "profile": {                          // null until generated
    "alias": "frost_magpie05", "archetype": "The Impersonator", "emoji": "🎭",
    "skill_level": "Advanced", "skill_desc": "...", "motivation": "...",
    "origin": "...", "crew_size": "...", "stealth": 0.88, "aggressiveness": 0.16,
    "preferred_ttps": ["..."], "toolset": ["..."], "mitre_tactics": ["..."]
  },
  "scenario": "# Penetration Test Scenario ... (markdown)",  // null until generated
  "report_url": "s3://tier2-data-reports.../reports/<scan_id>.md",  // null until DONE/FAILED
  "error": null,                        // string on FAILED/REJECTED
  "created_at": 1781094220,             // unix seconds
  "findings": [                         // grows while RUNNING; may span many endpoints
    {
      "finding_id": "1e4999...",
      "title": "Username Enumeration via Differential Error Messages",
      "severity": "medium",            // critical|high|medium|low|info (LOWERCASE)
      "endpoint": "https://api.cashlo.id:443/login",
      "evidence": "...",
      "poc": "curl ...",
      "remediation": "...",
      "attack_method": "differential error-message probing",
      "persona": "The Impersonator (frost_magpie05)"
    }
  ]
}
```

## 5. Statuses & polling

| Status | Meaning | Terminal? |
|---|---|---|
| `QUEUED` | accepted, starting | no |
| `RUNNING` | profile/scenario done; discovery + loop probing; findings streaming | no |
| `DONE` | finished; `report_url` set | yes |
| `FAILED` | error mid-run; `error` set; partial findings kept; report still written | yes |
| `REJECTED` | target not in the authorized allowlist; `error` set | yes |

Poll every **~15s**; stop on terminal. A full run now covers many endpoints, so
expect **~2–6 min**.

## 6. Errors

| Case | HTTP | Body |
|---|---|---|
| Bad/missing API key | `403` | `{"message":"Forbidden"}` |
| Unknown route | `403` | `{"message":"Missing Authentication Token"}` |
| `authorized` not true | `400` | `{"error":"Field 'authorized' must be true ..."}` |
| Bad port/ip/endpoint/scheme | `400` | `{"error":"Field '...' ..."}` |
| Malformed JSON | `400` | `{"error":"Body must be valid JSON."}` |
| Unknown scan id | `404` | `{"error":"scan not found"}` |
| Out-of-scope / runtime failure | — | surfaces via polling as `REJECTED`/`FAILED` + `error` |

## 7. TypeScript types
```ts
export type ScanStatus = "QUEUED" | "RUNNING" | "DONE" | "FAILED" | "REJECTED";
export type Severity = "critical" | "high" | "medium" | "low" | "info";

export interface ScopeResponse { targets: string[]; }

export interface LaunchRequest {
  ip: string; port: number; endpoint: string;
  scheme?: "http" | "https"; authorized: true;
}
export interface LaunchResponse { scan_id: string; status: "QUEUED"; }

export interface Profile {
  alias: string; archetype: string; emoji?: string; skill_level: string;
  skill_desc?: string; motivation: string; origin: string; crew_size: string;
  stealth: number; aggressiveness: number;
  preferred_ttps: string[]; toolset: string[]; mitre_tactics: string[];
}
export interface Finding {
  finding_id: string; title: string; severity: Severity; endpoint: string;
  evidence: string; poc?: string; remediation?: string;
  attack_method?: string; persona?: string;
}
export interface Scan {
  scan_id: string; status: ScanStatus; engine: string | null;
  target: { ip: string; port: number; endpoint: string; scheme: string; url: string };
  profile: Profile | null; scenario: string | null;
  report_url: string | null; error: string | null; created_at: number;
  findings: Finding[];
}
```

## 8. User stories

- **US1 Pick target:** As an operator I pick from a dropdown of permitted targets
  (`GET /scope`) so I don't type by hand; selecting fills host + port. A "Custom"
  option allows manual entry.
- **US2 Authorize:** I must tick a confirmation before launching.
- **US3 Launch:** I set the endpoint and launch; I get a `scan_id`.
- **US4 Live progress:** Status updates QUEUED→RUNNING→DONE automatically.
- **US5 See adversary:** I see the random attacker profile once generated.
- **US6 Read plan:** I read the Opus scenario (rendered markdown).
- **US7 Review findings:** Findings appear as they're reported, across multiple
  endpoints, sorted by severity, each with evidence/PoC/remediation.
- **US8 Report:** On DONE I get the `report_url`.
- **US9 Rejected/Failed:** Clear distinct states with `error`.
- **US10 Resilient polling:** Transient poll errors retry; `scan_id` preserved.

## 9. Screens / UX

1. **Launch form**
   - **Permitted target** dropdown from `GET /scope` (+ "Custom" manual option).
     Selecting `host:port` fills the host + port fields; CIDR entries disabled.
   - Host, Port, Endpoint fields (editable even after a dropdown pick = manual
     override). Optional scheme is auto-handled by the backend (443/8443→https);
     a scheme toggle is optional.
   - "I confirm I am authorized to test this target" checkbox; Launch disabled
     until ticked + host present.
2. **Run/progress** — status badge (QUEUED grey, RUNNING blue, DONE green,
   FAILED red, REJECTED amber); show `engine`, `created_at`; poll every 15s.
3. **Results (progressive)** — Profile card; Scenario (markdown); Findings list
   (group/sort by severity; show endpoint, evidence, poc, remediation); report link.
4. **States** — empty, loading, REJECTED banner, FAILED banner, connection-lost.

## 10. Behavior details

- Map `run_id ↔ scan_id`.
- Severity is **lowercase**.
- Findings array grows across polls — render idempotently keyed by `finding_id`;
  they may be on different endpoints (`finding.endpoint`).
- Poll ~15s, retry transient errors, stop on terminal.
- All requests send `x-api-key` (via your proxy).
- Don't send `run_id`/`domain`/`vector_id`/`options`/`callback_url` — ignored.
  `authorized:true` is mandatory. `scheme` is optional.

## 11. Safety copy

> This launches a real, bounded penetration test against the target you specify.
> Only run it against systems you are explicitly authorized to test. Targets are
> restricted to a server-side allowlist; unauthorized targets are rejected. Runs
> are rate-limited and capped (no denial-of-service).

## 12. Acceptance criteria

- [ ] Target dropdown populated from `GET /scope`; "Custom" enables manual entry.
- [ ] Launch blocked until authorized + host present.
- [ ] `POST /scan` → polling Run view; status auto-advances to terminal.
- [ ] Profile, scenario markdown, and multi-endpoint findings render from the
      poll payload (no extra endpoints).
- [ ] Findings sorted by severity with evidence/poc/remediation + endpoint shown.
- [ ] REJECTED and FAILED render distinct states with `error`.
- [ ] No domains/vectors/fraud/callbacks/tickets/options used anywhere.
- [ ] API key never in client bundle (proxy used).

## 13. Curl examples
```bash
# list permitted targets
curl "$BASE/scope" -H "x-api-key: $KEY"
# -> {"targets":["54.84.126.64:80","api.cashlo.id:443"]}

# launch (HTTP target)
curl -X POST "$BASE/scan" -H "Content-Type: application/json" -H "x-api-key: $KEY" \
  -d '{"ip":"54.84.126.64","port":80,"endpoint":"/login","authorized":true}'

# launch (HTTPS target — scheme inferred from port 443, or pass "scheme":"https")
curl -X POST "$BASE/scan" -H "Content-Type: application/json" -H "x-api-key: $KEY" \
  -d '{"ip":"api.cashlo.id","port":443,"endpoint":"/login","authorized":true}'
# -> 202 {"scan_id":"<id>","status":"QUEUED"}

# poll
curl "$BASE/scan/<id>" -H "x-api-key: $KEY"
```

## 14. Reference implementation
A working frontend implementing this exact contract is live at
`https://revamp-red-team.vercel.app` (repo `GreenLovePie/RevampRedTeam`,
`frontend/`). Use it as a reference.
