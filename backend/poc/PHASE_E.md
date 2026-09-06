# Phase E retrieval operation

Use the repository root and `backend/.venv/Scripts/python.exe` on Windows.
`RAG_MODE=disabled` is the default and preserves the non-vector development path.

## Offline demo

Set `APP_ENV=development`, `CALL_PROVIDER_MODE=fake`, and `RAG_MODE=fake` in the
process environment. Keep `DATABASE_URL` empty to use the ignored local SQLite DB.
Run the Alembic upgrade, then `python backend/poc/seed_demo_knowledge.py`.
Seeding is explicit and idempotent; five fictional policy/reference chunks are
stored. No real supplier facts or call artifacts are read.

Start `python -m uvicorn backend.app.main:app --host 127.0.0.1` and create a normal
sourcing request. `POST /api/v1/sourcing-requests/{id}/context-preview` returns
up to four chunks, source provenance, and composed task context without changing
approval state or making a call. The endpoint is disabled outside development/test.
SQLite stores fake vectors as JSON; Python performs cosine search. This is not
PostgreSQL/pgvector verification and the fake embedding is not a semantic model.

## PostgreSQL runtime boundary

Set `DATABASE_URL` to PostgreSQL and run `python -m alembic upgrade head` using
a migration role permitted to create the `vector` extension, or have an operator
preinstall it. Migration `e001_knowledge_chunks` creates `Vector(384)` storage.
Downgrade retains the extension to avoid disrupting other users of it.

`KnowledgeRepository` rejects SQLite and uses pgvector cosine distance (`<=>`),
ascending distance then chunk ID, with a limit of 1–5. Exact search is sufficient
for this small curated corpus; no approximate index is needed yet. It filters on
curation and embedding model identity to prevent mixing incompatible vectors.

The real embedding vendor remains intentionally unselected. Implement the
`EmbeddingProvider` protocol with a stable versioned `model_id`, 384 dimensions,
`embed_documents`, and `embed_query`; inject it into `build_retriever(session,
embeddings=provider)` at the application composition boundary. Use the same model
for ingestion and queries. Another dimension requires an explicit migration and
re-embedding; another model requires re-embedding the corpus. `RAG_MODE=postgres`
fails clearly until that provider is supplied; it never silently uses fake vectors.
The HTTP/graph composition currently supplies no real provider; wire that dependency
when the vendor is chosen. No paid embedding operation is part of Phase E.

Ingestion is an internal curated operation, not a public upload endpoint. Only
reviewed reference/policy material belongs here; source-type labels alone cannot
prove prose is safe. Never ingest quotes, transcripts, credentials, or live supplier
facts. Content is bounded to 2,000 characters per chunk. Keep source references
versioned and immutable after use in an approved preview; replace with a new version
instead of mutating an approved source. Source IDs persist on each request.

LangChain `PromptTemplate` only formats bounded context. LangGraph retrieves it
before preview. Provider request construction appends it to the existing quote task.
Ranking and result normalization do not receive knowledge inputs. Consent, purchase
prohibitions, both approval gates, and idempotency remain outside LangChain.

## Verification limits

Automated tests use deterministic fake embeddings and isolated SQLite. PostgreSQL
DDL and the cosine expression are compiled offline, and SQLite migrations are
round-trip tested on a temporary DB. Actual extension creation and vector retrieval
on PostgreSQL require an explicitly configured test instance and remain pending
when none is available. No infrastructure is installed automatically.
