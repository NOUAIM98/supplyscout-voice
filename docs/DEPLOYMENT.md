# SupplyScout Voice deployment

The production topology is Vercel (Next.js frontend) → Railway (FastAPI backend) → the existing Supabase PostgreSQL database with pgvector. Do not provision a Railway database.

## Railway backend

- Repository: `NOUAIM98/supplyscout-voice`
- Root directory: `backend`
- Build command: `pip install -r requirements.txt`
- Start command: `python -m app.knowledge.warmup && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health path: `/health`

Use these server-side environment variable names:

```dotenv
APP_ENV=production
CORS_ALLOWED_ORIGINS=http://localhost:3000
DATABASE_URL=<existing-supabase-postgresql-url>
RAG_MODE=postgres
RAG_EMBEDDING_PROVIDER=fastembed
RAG_EMBEDDING_MODEL=BAAI/bge-small-en-v1.5
RAG_EMBEDDING_CACHE_DIR=/tmp/fastembed_cache
CALL_PROVIDER_MODE=fake
CALLE_LIVE_ENABLED=false
CALLE_ALLOWED_RECIPIENTS=
CALLE_BASE_URL=https://api.heycall-e.com
```

The warm-up command downloads the 384-dimensional FastEmbed model into a normal writable container cache and validates one embedding before Uvicorn starts. The cache is not committed and a fresh container can recreate it. `CALLE_API_KEY`, test-phone variables, and live-test confirmation are not required in safe demo mode.

After the Vercel production domain is known, set `CORS_ALLOWED_ORIGINS` to a comma-separated allowlist such as:

```dotenv
CORS_ALLOWED_ORIGINS=http://localhost:3000,https://<actual-vercel-domain>
```

Never use a wildcard origin.

## Vercel frontend

- Repository: `NOUAIM98/supplyscout-voice`
- Root directory: `frontend`
- Framework: Next.js
- Build command: `npm run build`
- Environment variable: `NEXT_PUBLIC_API_URL=https://<actual-railway-domain>`

Only the public backend URL belongs in Vercel. Database credentials, CALL-E settings, and server-side RAG configuration remain on Railway.
