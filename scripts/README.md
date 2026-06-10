# Tier2 Operator Scripts

Helper scripts for operating the Tier2 backend. They cover two things:
managing the **scope allowlist** (which targets a scan is allowed to hit) and
**building the Lambda dependency layer** for deploys.

| Script | Shell | What it does |
|--------|-------|--------------|
| [`register_target.sh`](#register_targetsh) | bash | Add / remove / list a single `host:port` in the scope allowlist (append + dedupe) |
| [`set_scope.ps1`](#set_scopeps1) | PowerShell | **Replace** the entire scope allowlist in one call |
| [`build_layer.ps1`](#build_layerps1) | PowerShell | Build the Lambda dependency layer (`build/layer/python`) before `cdk deploy` |

## Background: the scope allowlist

The backend is **fail-closed**. Every scan calls `assert_in_scope(target)`
against an SSM parameter (`/tier2/scope-allowlist`, a `StringList`). A scan is
only allowed if the target's `host:port` matches an entry; an empty or unset
allowlist rejects everything. Out-of-scope scans end with `status: REJECTED`.

An entry may be:
- a bare host — `54.84.126.64`
- a `host:port` — `54.84.126.64:80`
- a CIDR range — `10.0.0.0/24`

> The execution loop targets `http://<ip>:<port>`. HTTPS targets are not
> supported yet — register the `host:port`, but reaching it over HTTPS needs a
> backend change.

## Prerequisites

- **AWS CLI v2** with credentials that can read/write the SSM parameter
  (`ssm:GetParameter`, `ssm:PutParameter`).
- Region defaults to `us-east-1`. Override with `AWS_REGION` / `AWS_DEFAULT_REGION`.
- Parameter name defaults to `/tier2/scope-allowlist`. Override with
  `SCOPE_PARAM_NAME`.
- `register_target.sh` runs in **bash** (Linux/macOS, or **Git Bash**/WSL on
  Windows). The `.ps1` scripts run in **PowerShell**.

---

## `register_target.sh`

Add (default), remove, or list a single `host:port` in the allowlist. Unlike
`set_scope.ps1`, it **appends and de-duplicates** instead of overwriting, so you
can register targets incrementally.

### Usage
```bash
bash scripts/register_target.sh <ip-or-domain> <port>            # add
bash scripts/register_target.sh <ip-or-domain> <port> --remove   # remove
bash scripts/register_target.sh --list                           # show current
bash scripts/register_target.sh --help
```

### Examples
```bash
# register an IP + port
bash scripts/register_target.sh 54.84.126.64 80

# register a domain + port
bash scripts/register_target.sh sandbox-defender.example.com 443

# remove an entry
bash scripts/register_target.sh 10.0.0.5 8080 --remove

# list current allowlist
bash scripts/register_target.sh --list

# different region / parameter name
AWS_REGION=ap-southeast-1 SCOPE_PARAM_NAME=/tier2/scope-allowlist \
  bash scripts/register_target.sh 10.0.0.5 8080
```

### Sample output
```
$ bash scripts/register_target.sh 10.0.0.5 8080
Registering 10.0.0.5:8080 ...
Allowlist for /tier2/scope-allowlist is now:
  - 54.84.126.64:80
  - 10.0.0.5:8080

$ bash scripts/register_target.sh 10.0.0.5 8080
'10.0.0.5:8080' is already registered; nothing to do.

$ bash scripts/register_target.sh 10.0.0.5 8080 --remove
Removing 10.0.0.5:8080 ...
Allowlist for /tier2/scope-allowlist is now:
  - 54.84.126.64:80
```

### Behavior & safeguards
- **Validation:** rejects invalid IPv4 (octets > 255) / malformed domains, and
  ports outside `1–65535`.
- **Dedupe:** adding an existing entry is a no-op.
- **Fail-closed:** refuses to write an empty allowlist (use `set_scope.ps1` if you
  intend to reset).
- **Windows-safe:** sets `MSYS_NO_PATHCONV=1` so Git Bash doesn't mangle the
  leading-slash SSM parameter name (`/tier2/...`).

### Exit codes
`0` success · `1` validation/usage/AWS error (message printed to stderr).

---

## `set_scope.ps1`

**Replaces** the entire allowlist with one value (overwrite). Use when you want a
single authorized target and don't care about existing entries.

```powershell
.\scripts\set_scope.ps1 -Scope "54.84.126.64:80"
# multiple entries (comma-separated):
.\scripts\set_scope.ps1 -Scope "54.84.126.64:80,10.0.0.0/24"
```

---

## `build_layer.ps1`

Builds the Lambda dependency layer into `build/layer/python` from
`backend/requirements-lambda.txt`. Run it before `npx cdk deploy` whenever the
Lambda dependencies change.

```powershell
.\scripts\build_layer.ps1
```

---

## Typical flow

```bash
# 1. authorize a target
bash scripts/register_target.sh 54.84.126.64 80

# 2. confirm it's registered
bash scripts/register_target.sh --list

# 3. launch a scan (see repo README / docs/frontend-integration-prompt.md)
curl -X POST "$BASE/scan" -H "x-api-key: $KEY" -H "Content-Type: application/json" \
  -d '{"ip":"54.84.126.64","port":80,"endpoint":"/login","authorized":true}'
```
