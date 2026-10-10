# SupplyScout Voice

> The procurement agent for businesses whose supplier data still lives on the phone.

SupplyScout Voice helps small businesses source urgent inventory and parts without manually calling every supplier. The demo vertical follows an independent auto repair shop sourcing an urgent alternator for a 2019 Renault Clio.

## Live demo

- Frontend: [supplyscout-voice.vercel.app](https://supplyscout-voice.vercel.app)
- Backend health: [supplyscout-voice-production.up.railway.app/health](https://supplyscout-voice-production.up.railway.app/health)

## Workflow

1. Create a sourcing request.
2. Retrieve bounded procurement context.
3. Preview the call plan and explicitly approve supplier calls.
4. CALL-E makes outbound calls to approved suppliers.
5. Poll CALL-E and normalize structured results while preserving unknown facts.
6. Rank quotes with deterministic business rules.
7. Let the human choose a supplier.
8. Require separate approval before a reservation call.

SupplyScout never makes a payment or autonomous purchase.

## Where CALL-E fits

CALL-E performs the actual outbound supplier phone calls. SupplyScout provides CALL-E with the structured task, recipient, result schema, and idempotency key. The backend then polls CALL-E and normalizes its structured results for comparison and selection.

## Architecture

```mermaid
flowchart LR
    UI[Next.js / TypeScript<br/>Vercel] --> API[FastAPI / Python<br/>Railway]
    API --> GRAPH[LangGraph<br/>approval workflow]
    GRAPH --> RAG[LangChain + FastEmbed<br/>bounded context]
    RAG --> DB[(PostgreSQL / Supabase<br/>pgvector)]
    GRAPH --> CALL[CALL-E<br/>phone-call runtime]
    CALL --> API
    API --> RANK[Deterministic<br/>ranking]
```

- **Frontend:** Next.js and TypeScript, deployed on Vercel
- **Backend:** FastAPI and Python, deployed on Railway
- **Data:** PostgreSQL on Supabase with pgvector
- **Orchestration:** LangGraph
- **Retrieval and composition:** LangChain with bounded context
- **Embeddings:** FastEmbed using `BAAI/bge-small-en-v1.5`
- **Voice runtime:** CALL-E

## Safety

- Explicit human approval before outbound calls
- Strict recipient allowlist and E.164 validation
- Separate approval before reservation calls
- Idempotency protection for call dispatch
- No payments or autonomous purchases
- Unknown and uncertain supplier facts remain unknown
- Credentials remain server-side
- Fake provider mode for demos and tests

## Controlled live proof

A controlled production call to the official CALL-E US hackathon test hotline reached terminal status `completed`. CALL-E returned a real provider call ID, and SupplyScout normalized the result while correctly preserving unavailable supplier facts as unknown. No private phone number or provider call ID is included in this repository.

## Demo flow for judges

1. Open the frontend and create the prefilled Renault Clio alternator demo request.
2. Review the bounded context, its general/reference-specific scope, and the fictional supplier-call preview.
3. Approve simulated quote requests at the explicit human gate. This never invokes CALL-E.
4. Review all normalized offers; unconfirmed or unavailable offers remain visible but cannot be ranked or selected.
5. Select an eligible supplier, review the separate reservation approval, and complete the fictional reservation.
6. Return to the overview to resume the most recent request, or paste any request ID.

The portfolio UI creates requests through the isolated `/api/v1/demo/sourcing-requests` endpoint. Demo identity is persisted in the audit trail, so every later quote and reservation operation for that request remains on the fake provider even when the deployment is configured for CALL-E.
The backend also defaults to `PORTFOLIO_DEMO_ONLY=true`, which blocks real CALL-E dispatch even if live-provider settings are accidentally present. Demo request creation is throttled per client as a lightweight abuse safeguard.

### What remains simulated

- Supplier identities, quote facts, prices, availability, warranties, and reservation references are fictional fixtures.
- The demo performs no phone call, payment, purchase, or external network operation.
- The hardcoded quote fixture is exact only for `TEST-ALT-CLIO-2019-001`. A custom reference produces no false exact match and may correctly yield no eligible quote.
- Reference-specific knowledge is included only when its reference matches the request; general procurement policy remains available independently.

### Production limitations

- Real CALL-E requests remain separately guarded by server-side mode, live-enable, recipient allowlist, E.164, approval, and idempotency checks.
- This portfolio build has no user-account authorization. It is suitable only for fictional demo data; production procurement would require authenticated users, tenant isolation, durable distributed rate limiting, and a retention policy.
- The included demo throttle is process-local. Configure an edge or gateway rate limit before exposing a horizontally scaled deployment.
- Fictional requests persist in the configured database until they are removed by an operator; automated retention is not implemented.
- CALL-E completion is polled by the backend; there is no background worker or webhook-driven refresh in this demo architecture.
- The resume shortcut is browser-local. A request can always be reopened directly when its ID is known.

## Local setup

Prerequisites: Python 3.11+, Node.js 20+, and PostgreSQL when using database-backed retrieval.

### Backend

```bash
python -m venv backend/.venv
backend/.venv/Scripts/python -m pip install -r backend/requirements.txt
```

Create `backend/.env` with placeholder or local-only values:

```dotenv
APP_ENV=development
CORS_ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=postgresql+psycopg://<user>:<password>@<host>:<port>/<database>
PORTFOLIO_DEMO_ONLY=true
DEMO_CREATE_RATE_LIMIT=10
DEMO_CREATE_RATE_WINDOW_SECONDS=3600
RAG_MODE=disabled
RAG_EMBEDDING_PROVIDER=fastembed
RAG_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RAG_EMBEDDING_CACHE_DIR=<local-cache-directory>
CALL_PROVIDER_MODE=fake
CALLE_API_KEY=<server-side-api-key>
CALLE_BASE_URL=https://api.heycall-e.com
CALLE_LIVE_ENABLED=false
CALLE_ALLOWED_RECIPIENTS=<comma-separated-e164-allowlist>
CALLE_RECIPIENT_REGION=<supported-region>
CALLE_RECIPIENT_LOCALE=<supported-locale>
```

Start the API from the repository root:

```bash
backend/.venv/Scripts/python -m uvicorn backend.app.main:app --reload
```

For macOS or Linux, use `backend/.venv/bin/python` instead.

### Frontend

```bash
cd frontend
npm install
```

Create `frontend/.env.local`:

```dotenv
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Then start the app:

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Verification

```bash
backend/.venv/Scripts/python -m pytest backend/tests
cd frontend
npm test
npm run lint
npm run typecheck
npm run build
```
