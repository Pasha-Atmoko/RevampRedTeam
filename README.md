# SuperAI NEXT — AI-Driven Pentest Scenario & Execution

2-tier app: a Next.js/Vercel frontend submits a target (IP, port, endpoint); an
AWS backend generates a **random attacker profile**, uses **Bedrock + Claude
Opus** to author a **pentest scenario**, then **executes** it against the
authorized target via an Opus-driven tool-use loop.

> ⚠️ **Offensive tooling.** Only run against systems you own or are explicitly
> authorized to test. Controls enforced in code: authorization gate, fail-closed
> scope allowlist (SSM), audited rate-limited HTTP client, hard request caps, no
> DoS. See the design spec in `docs/superpowers/specs/`.

## Architecture
API Gateway (REST + API key + CORS) → SubmitScan λ → Step Functions Standard
(`ValidateScope → ProfileAndScenario → ExecuteAttack (VPC) → Report`) →
DynamoDB + S3. Frontend polls `GET /scan/{id}`.

## Backend tests
```bash
cd backend && python -m venv .venv && .venv/Scripts/python -m pip install -r requirements-dev.txt
.venv/Scripts/python -m pytest -v
```

## Deploy (AWS)
```powershell
cd Tier2
backend\.venv\Scripts\python -m pip install -r backend\requirements.txt
.\scripts\build_layer.ps1
npx cdk bootstrap          # first time per account/region
npx cdk deploy --all       # outputs ApiUrl + ApiKeyValue
# Enable Bedrock Opus model access in the console for your region.
.\scripts\set_scope.ps1 -Scope "54.84.126.64:8080"   # fail-closed until set
```

## Frontend (Vercel)
```bash
cd frontend && cp .env.local.example .env.local
# set NEXT_PUBLIC_API_BASE = <ApiUrl>  and  NEXT_PUBLIC_API_KEY = <ApiKeyValue>
npm install && npm run dev            # local dev
vercel deploy                         # deploy
```
The REST API CORS allows all origins by default; tighten to your Vercel origin
in `infra/orchestration_stack.py` for production.

## Local backend smoke (no AWS)
```bash
cd backend && .venv/Scripts/python run_local.py http://TARGET:PORT --endpoint /login --scope TARGET:PORT --yes
```

## Security notes
- Simple API-key mode ships the key to the browser (demo). To hide it, add Next.js
  `app/api/scan/*` proxy routes that hold the key server-side and point `lib/api.ts`
  at `/api/scan`.
- Tighten the egress security group (`infra/network_stack.py`) to the target CIDR
  for production.
