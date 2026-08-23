# SupplyScout Voice MVP Architecture

This document defines the implementation architecture for the scope locked in `MVP.md`. If this document and `MVP.md` conflict, `MVP.md` wins. This phase defines architecture only; it does not authorize implementation or scope expansion.

## 1. Architecture Goals

- Deliver the complete automotive-parts sourcing and reservation flow defined in `MVP.md`.
- Make CALL-E essential to real quote collection and reservation while keeping all authenticated provider access server-side.
- Support three or more supplier calls concurrently without blocking the browser.
- Preserve structured facts, unknown values, uncertainty, and terminal call outcomes.
- Enforce explicit, auditable approval before quote calls and a separate approval before reservation.
- Produce deterministic, explainable quote eligibility and ranking.
- Stay small enough to build, test, deploy, and demonstrate during a hackathon.
- Provide a fake provider that exercises the same application path without making a call.

## 2. Architecture Principles

1. **`MVP.md` is the scope contract.** Automotive parts for independent repair shops are the only MVP vertical.
2. **Human approval is a server-enforced invariant.** UI controls alone are not authorization.
3. **Provider isolation.** Application services use a CALL-E adapter interface rather than provider-specific behavior throughout the codebase.
4. **Asynchronous by default.** Provider calls run in workers; HTTP requests enqueue work and return promptly.
5. **Database-backed truth.** PostgreSQL owns approvals, attempts, results, selections, outcomes, and audit records. Redis transports jobs but is not the system of record.
6. **Idempotent boundaries.** Approval commands, job execution, and webhook ingestion tolerate repeated delivery.
7. **Unknown stays unknown.** Missing or unclear supplier statements are never converted into asserted facts.
8. **Deterministic decisions.** Eligibility and ranking are versioned pure application logic, not an LLM judgment.
9. **Minimal infrastructure.** No Kubernetes, Kafka, microservices, GraphQL, service mesh, or event sourcing.
10. **Privacy by default.** Credentials stay server-side and phone numbers are masked outside narrowly authorized operations.
11. **Agent orchestration is not business truth.** LangGraph coordinates resumable workflow and LangChain supplies AI utilities; PostgreSQL constraints and deterministic Python services enforce approvals, idempotency, facts, and ranking.

## 3. Technology Stack

| Layer | Choice | MVP role |
| --- | --- | --- |
| Frontend | Next.js, TypeScript | Web routes, server-rendered shell, client interactions |
| UI | Tailwind CSS, shadcn/ui | Small accessible component set |
| Server state | TanStack Query | Fetching, mutation status, polling, cache invalidation |
| API | FastAPI, Python, Pydantic | REST contract, validation, application services, webhooks |
| Agent orchestration | LangGraph | Stateful, resumable human-in-the-loop sourcing workflow inside the backend |
| AI utilities | LangChain | Model abstraction, prompt/context construction, structured outputs, and retrieval integration |
| Persistence | PostgreSQL with pgvector, SQLAlchemy, migrations | Authoritative workflow data, constraints, and limited curated RAG context |
| Background execution | Redis plus a lightweight Python worker (RQ) | Concurrent quote/reservation jobs and explicit retries |
| Phone provider | CALL-E Developer API through a server-side adapter | Real outbound calls and results |
| Frontend hosting | Vercel | Next.js deployment |
| API and worker hosting | Railway | Separate API and worker processes from one backend artifact |
| Managed data | Managed PostgreSQL and managed Redis | Durable data and queue transport |

The CALL-E SDK or CLI may be used locally for proof-of-concept work. Production application calls use the server-side Developer API adapter unless the POC proves a concrete incompatibility.

## 4. High-Level System Architecture

The browser communicates only with the FastAPI REST API. Inside the FastAPI/worker backend, one SupplyScout Procurement Agent uses LangGraph to orchestrate the sourcing workflow and human approval checkpoints. LangChain supplies model, structured-output, context, and retrieval utilities; it does not own business truth. FastAPI validates commands and records authoritative approvals and workflow data in PostgreSQL. The agent enqueues approved work in Redis, and lightweight Python workers invoke either the real CALL-E adapter or the fake adapter. CALL-E sends terminal events to a public FastAPI webhook when supported; the API validates, deduplicates, and applies them to PostgreSQL. The frontend reads progress and results from FastAPI using short polling through TanStack Query.

```text
Browser
  -> Next.js on Vercel
  -> FastAPI on Railway
       -> Procurement Agent (LangGraph orchestration)
            -> LangChain utilities -> curated pgvector context
            -> PostgreSQL (system of record + LangGraph checkpoints)
            -> Redis queue -> Python worker -> CALL-E Developer API -> supplier phone
       <- CALL-E webhook ---------------------------------------|
       -> fake CALL-E adapter (development/test alternative)
```

The frontend never invokes CALL-E, receives provider credentials, or decides whether an approved call may execute.

## 5. Repository / Monorepo Structure

Planned structure; it is not created during the architecture phase:

```text
/
├── MVP.md
├── ARCHITECTURE.md
├── apps/
│   ├── web/                 # Next.js frontend
│   ├── api/                 # FastAPI HTTP entry point
│   └── worker/              # RQ worker entry point
├── packages/
│   └── contracts/           # Generated/exported API types if adopted
├── backend/
│   ├── domain/              # entities, enums, state rules
│   ├── application/         # commands, queries, ranking, normalization
│   │   ├── agent/           # LangGraph sourcing workflow and checkpoints
│   │   └── ai/              # LangChain model, structured-output, and retrieval utilities
│   ├── infrastructure/      # SQLAlchemy, Redis, CALL-E adapters
│   └── tests/
└── docs/                    # future approved supporting documentation
```

The API and worker share the same Python domain/application/infrastructure modules. They are separate processes, not separate services or independently evolving systems.

## 6. Frontend Architecture

The MVP frontend has a small set of workflow-focused views:

- Supplier registration/selection with masked number and authorization status.
- Sourcing request form for vehicle, part, quantity, budget, and deadline.
- Quote-call preview showing the request and selected suppliers without exposing full numbers unnecessarily.
- Explicit quote-call approval action.
- Request progress/results view showing each call state, structured quote, review/exclusion reasons, comparison, and recommendation.
- Human offer-selection action.
- Reservation preview and separate approval action.
- Reservation status and structured terminal outcome.

Next.js owns presentation and navigation only. TanStack Query performs REST reads/mutations and polls the request results endpoint while any call is nonterminal. The server remains authoritative after every mutation. Approval buttons must prevent casual double submission, but backend constraints provide actual duplicate prevention.

No generic chatbot, supplier discovery, analytics suite, payment UI, or autonomous purchase control exists.

## 7. Backend Architecture

FastAPI is organized as a modular monolith:

- **HTTP layer:** Pydantic request/response validation, authentication context, status codes, webhook endpoint.
- **Procurement Agent:** a server-side LangGraph workflow inside the application layer; it orchestrates sourcing stages and resumable human checkpoints but is not a separate service.
- **Application layer:** sourcing commands, preview generation, approvals, offer selection, reservation commands, normalization, ranking, retrieval boundaries, and audit emission.
- **Domain layer:** entities, state transitions, eligibility rules, value objects such as E.164 numbers and money.
- **AI utility layer:** narrowly scoped LangChain model abstraction, prompt/context construction, structured outputs, and retrieval integration.
- **Infrastructure layer:** SQLAlchemy repositories, PostgreSQL/pgvector transactions and checkpoints, Redis/RQ, CALL-E and fake provider adapters.

The Procurement Agent maintains the sourcing workflow, constructs the sourcing goal, assembles curated context, enforces human approval checkpoints, dispatches approved CALL-E tasks, processes structured results, coordinates normalization, waits for manual selection, and coordinates the separately approved reservation workflow. PostgreSQL and deterministic domain services—not LangGraph or LangChain—remain authoritative for approvals, idempotency, quote facts, and ranking.

Mutation services run in database transactions. They validate ownership/authorization, current state, approval evidence, and idempotency before writing. Provider calls never occur inside an HTTP database transaction; the transaction commits an attempt and resumable checkpoint before a job is enqueued.

## 8. Background Job Architecture

Quote approval advances the Procurement Agent from its approval checkpoint, creates one queued `CallAttempt` per approved supplier, and enqueues one job per attempt. RQ allows separate jobs to run independently, so a slow or unanswered supplier does not block other suppliers.

Each job:

1. Loads the attempt from PostgreSQL.
2. Returns safely if the attempt is already terminal or already has a provider call identifier.
3. Revalidates recorded approval, supplier authorization, and attempt type.
4. Atomically claims the queued attempt.
5. Calls the configured provider adapter with a strict result schema and correlation metadata.
6. Stores the provider call identifier and `calling` state.
7. Awaits webhook completion when supported; otherwise a bounded reconciliation job obtains the terminal result.

Reservation jobs use the same path but require a reservation approval and reference the selected quote. Worker concurrency remains deliberately small and configurable. Redis loss may delay jobs but cannot erase authoritative approvals or outcomes.

Webhook delivery, asynchronous completion callbacks, result retrieval, metadata echoing, and provider-side concurrency behavior are **VERIFY DURING CALL-E POC**.

## 9. CALL-E Integration Architecture

Define a server-side `CallProvider` interface with two commands:

- `start_quote_call(call_attempt, supplier, sourcing_request, result_schema)`
- `start_reservation_call(call_attempt, supplier, selected_quote, result_schema)`

Implementations:

- `CallEProvider`: authenticated Developer API integration used for real calls.
- `FakeCallProvider`: deterministic fixtures used for preview-safe development and automated tests.

The Procurement Agent uses LangChain utilities to assemble the sourcing goal, permitted curated context, call constraints, and output schema before dispatch. The CALL-E adapter then builds the provider request, requires the phone agent to identify itself as AI, requests only MVP fields, attaches non-sensitive correlation metadata, and requests the appropriate structured schema. Payment information and purchasing authority are never included.

CALL-E remains the essential AI phone-agent runtime: it performs the actual live supplier conversation and returns structured results. LangGraph orchestrates SupplyScout's business workflow around those calls, and LangChain supports context and structured interaction; neither replaces CALL-E.

The following are **VERIFY DURING CALL-E POC**:

- Developer API endpoints, authentication form, SDK compatibility, and rate limits.
- Whether CALL-E accepts a JSON Schema directly and how strictly it enforces it.
- Provider call identifiers, metadata limits, and metadata returned in events.
- Webhook availability, event types, delivery order, retry policy, and signature verification.
- Exact mappings for answered, completed, no-answer, refused, and provider failure outcomes.
- Whether a terminal result must be fetched after an event rather than included in it.
- Provider support for a completion-confidence value; absence must remain `null`, not fabricated.

Provider payloads are mapped into internal contracts at the adapter boundary. Provider-specific payload shapes must not leak into the frontend or ranking engine.

## 10. Sourcing Request Workflow

1. An authenticated user manually registers/selects authorized suppliers.
2. The user creates one sourcing request with vehicle, part, quantity, budget, currency, and required-by deadline.
3. The user selects suppliers belonging to the request context.
4. The API validates supplier activation and E.164 numbers, then generates a versioned preview and audit event.
5. The frontend displays the preview and performs no real call.
6. The user submits explicit quote-call approval referencing that preview.
7. The API atomically records approval; the Procurement Agent resumes, creates queued attempts, writes the approval audit event, and enqueues jobs.
8. The agent waits for structured terminal results while the user observes durable statuses.
9. When results change, the agent coordinates normalization and deterministic comparison using domain services.
10. The agent pauses for the user to manually select a valid or reviewable quote with the displayed status and reasons.
11. The agent coordinates the reservation preview, separate approval checkpoint, CALL-E reservation task, and stored outcome.

Changing call-relevant request or supplier data invalidates an older preview and requires a new preview and approval.

## 11. Supplier Quote Call Workflow

For each selected supplier:

1. Quote approval produces one logical call keyed by `(sourcing_request_id, supplier_id)` and an initial tracked attempt.
2. The worker starts the real or fake call only after verifying approval and authorization.
3. The attempt moves `queued` → `calling`.
4. A terminal provider result moves it to `completed`, `no_answer`, or `failed`.
5. A completed structured quote is validated, normalized, stored once, classified as `valid`, `human_review`, or `excluded`, and audited.
6. Ranking is regenerated from currently valid quotes only.

An explicit user retry creates a new attempt number under the same logical call. It does not overwrite the earlier attempt or result. No-answer and failed attempts do not produce invented quote facts.

## 12. Reservation Call Workflow

1. The user selects a stored quote; the selection and reasons/status visible at selection time are recorded.
2. The API creates or updates the single logical reservation for `(sourcing_request_id, selected_quote_id)` in `pending_approval`.
3. The API generates a reservation preview. No call occurs.
4. The user separately approves that exact reservation preview.
5. The API records approval and creates the initial reservation `CallAttempt`.
6. The worker calls only the selected quote's supplier and asks only for reservation, never payment or purchase.
7. The reservation becomes `calling`, then one of `confirmed`, `refused`, `unavailable`, `unclear`, `no_answer`, or `failed`.
8. A confirmed result stores the supplier reference when supplied; absence of a reference remains explicit.

Explicit reservation retries create new tracked attempts but do not replace prior history.

## 13. State Machines

### Quote `CallAttempt`

```text
queued -> calling -> completed
                  -> no_answer
                  -> failed
queued ----------------> failed
```

Terminal states are `completed`, `no_answer`, and `failed`. Repeated webhook events cannot move a terminal attempt backward. An explicit retry creates a new attempt rather than reopening one.

### Reservation

```text
pending_approval -> calling -> confirmed
                            -> refused
                            -> unavailable
                            -> unclear
                            -> no_answer
                            -> failed
```

The same terminal monotonicity rule applies. A retry is represented by another reservation call attempt while the reservation retains history and reflects the latest deliberate attempt's outcome.

### Sourcing request projection

The request UI status is derived from approvals, attempts, quotes, selection, and reservation instead of maintained as a second complex state machine. Suggested projections are `draft`, `awaiting_quote_approval`, `collecting_quotes`, `quotes_ready`, `offer_selected`, `awaiting_reservation_approval`, `reserving`, and `finished`.

### Procurement Agent workflow (LangGraph)

The server-side Procurement Agent uses a resumable graph conceptually ordered as:

```text
request_created
  -> context_retrieval
  -> call_preview
  -> awaiting_quote_approval
  -> supplier_calls_dispatched
  -> awaiting_results
  -> quotes_normalized
  -> ranked
  -> awaiting_human_selection
  -> reservation_preview
  -> awaiting_reservation_approval
  -> reservation_call
  -> completed
```

These are orchestration stages and checkpoints, not required database enums. LangGraph may pause and resume around human actions and asynchronous results, but every transition that authorizes a call is revalidated against authoritative PostgreSQL approval records. Checkpoints support resumption; they do not replace domain entities, audit events, or call-attempt state machines.

## 14. Database Model

All identifiers are UUIDs; timestamps are UTC. Mutable records include optimistic versioning or guarded updates where concurrent writes matter. PostgreSQL remains authoritative for application data and LangGraph checkpoints; pgvector is enabled only for the limited curated knowledge layer described below.

### `Supplier`

- `id`, `owner_user_id`, `display_name`
- `phone_e164` (validated canonical E.164)
- `call_authorized`, `authorized_at`, `authorized_by_user_id`
- `is_active`, `created_at`, `updated_at`

Unique active phone number per owner context. Full numbers are encrypted at rest when supported by the deployment and never returned in ordinary response models; masked values are derived server-side.

### `SourcingRequest`

- `id`, `owner_user_id`
- `vehicle_make`, `vehicle_model`, `vehicle_year`
- `part_name`, `exact_reference` nullable, `quantity`
- `maximum_budget_amount`, `maximum_budget_currency`
- `required_by`
- preview version/hash and quote approval actor/time
- selected `SupplierQuote` ID nullable
- `created_at`, `updated_at`

Supplier selections use a small join table between sourcing requests and suppliers. It is an implementation table, not an additional product concept.

### `CallAttempt`

- `id`, `sourcing_request_id`, `supplier_id`
- `kind`: `quote` or `reservation`
- `reservation_id` nullable, `supplier_quote_id` nullable
- `logical_key`, `attempt_number`, `explicit_retry`
- `status`: `queued`, `calling`, `completed`, `no_answer`, `failed`
- approval reference/time, provider call ID nullable
- provider error code/message sanitized, started/completed timestamps
- `created_at`, `updated_at`

Unique constraints cover `(logical_key, attempt_number)`, provider call ID when present, and command idempotency keys. A reservation attempt must reference its reservation and selected quote.

### `SupplierQuote`

- `id`, unique `call_attempt_id`, `sourcing_request_id`, `supplier_id`
- normalized quote fields from Section 16
- classification: `valid`, `human_review`, or `excluded`
- machine-readable reason codes and human-readable explanation
- ranking policy version and comparison snapshot fields as needed
- restricted original structured result for debugging/audit, subject to retention policy
- `created_at`, `updated_at`

### `Reservation`

- `id`, `sourcing_request_id`, `selected_quote_id`, `supplier_id`
- `status`: all states defined in Section 13
- preview version/hash, approved by/at
- supplier reservation reference nullable
- result notes and uncertainty fields
- `created_at`, `updated_at`

Unique logical reservation constraint on `(sourcing_request_id, selected_quote_id)`.

### `AuditEvent`

- `id`, `sourcing_request_id`, `actor_user_id` nullable for system/provider
- `event_type` restricted to the events locked in `MVP.md`
- `entity_type`, `entity_id`, timestamp
- minimal redacted metadata; no secrets and no unmasked phone number

### Relationships

- A user owns many `Supplier` and `SourcingRequest` records.
- A `SourcingRequest` selects many `Supplier` records through the join table.
- A `SourcingRequest` has many `CallAttempt`, `SupplierQuote`, and `AuditEvent` records.
- A `Supplier` has many quote `CallAttempt` and `SupplierQuote` records.
- A completed quote `CallAttempt` has at most one `SupplierQuote`.
- A `SourcingRequest` selects at most one current `SupplierQuote`.
- A `Reservation` belongs to one sourcing request, one selected quote, and its supplier.
- A `Reservation` has one or more tracked reservation `CallAttempt` records when explicitly retried.

An internal webhook-deduplication record may store provider event IDs and payload hashes; it is operational infrastructure, not a product entity.

### Limited RAG knowledge storage

Small supporting document/chunk tables may store curated text, source metadata, versions, and pgvector embeddings. Permitted context includes automotive part/reference notes, vehicle/reference context, procurement-call instructions, approved substitution rules, user-provided compatibility information, and call policy/safety constraints.

RAG is contextual evidence only. It is never authoritative for current supplier stock, live price, current delivery time, current warranty, or reservation confirmation; those facts must come from CALL-E supplier conversations. Retrieved context must identify its source and must not claim an exact match when uncertain. RAG never ranks quotes or selects a supplier.

## 15. API Contract

All endpoints are versioned under `/api/v1`. Ordinary responses use masked phone numbers. Mutations accept a client idempotency key and return the authoritative current resource.

| Method and path | Purpose |
| --- | --- |
| `POST /suppliers` | Manually register a supplier and assert/record call authorization |
| `GET /suppliers` | List selectable suppliers with masked numbers and authorization state |
| `PATCH /suppliers/{supplier_id}/authorization` | Activate or deactivate outbound-call authorization; no call is started |
| `POST /sourcing-requests` | Create a sourcing request and selected supplier IDs |
| `GET /sourcing-requests/{request_id}` | Read request, selection, derived status, and approval state |
| `POST /sourcing-requests/{request_id}/quote-preview` | Validate current data and generate a versioned no-call preview |
| `POST /sourcing-requests/{request_id}/quote-calls/approve` | Explicitly approve the preview, create attempts, and enqueue quote calls |
| `POST /sourcing-requests/{request_id}/quote-calls/{supplier_id}/retry` | Explicitly create one tracked retry after an eligible terminal attempt |
| `GET /sourcing-requests/{request_id}/results` | Return call progress, structured quotes, classifications, comparison, and recommendation |
| `POST /sourcing-requests/{request_id}/selection` | Manually select a quote; never auto-select |
| `POST /sourcing-requests/{request_id}/reservation-preview` | Generate a versioned no-call preview for the selected quote |
| `POST /sourcing-requests/{request_id}/reservation/approve` | Separately approve and enqueue the reservation call |
| `POST /sourcing-requests/{request_id}/reservation/retry` | Explicitly create one tracked reservation retry |
| `POST /webhooks/call-e` | Receive provider events; provider-authenticated, not a browser endpoint |

No general-purpose update/delete CRUD, payment, purchase, discovery, marketplace, CRM, or analytics endpoints are part of the MVP. Exact HTTP bodies and response schemas will be derived from the entity and result contracts before implementation.

## 16. Structured CALL-E Result Contracts

These are SupplyScout's provider-neutral JSON contracts. Whether CALL-E can emit them directly or requires adapter-side mapping is **VERIFY DURING CALL-E POC**.

### A. Supplier quote result

```json
{
  "schema_version": "1.0",
  "call_attempt_id": "uuid",
  "call_outcome": "completed",
  "quote": {
    "exact_reference": "confirmed | not_confirmed | unclear",
    "availability": "in_stock | unavailable | unclear",
    "condition": "new | used | remanufactured | other | unclear",
    "manufacturer_brand": "string | null",
    "quantity_available": "integer | null",
    "unit_price": "decimal-string | null",
    "currency": "ISO-4217-string | null",
    "tax_inclusion": "included | excluded | unclear",
    "warranty": {
      "status": "offered | none | unclear",
      "duration_months": "integer | null",
      "description": "string | null"
    },
    "pickup": {
      "available": "boolean | null",
      "earliest_at": "ISO-8601-datetime | null",
      "notes": "string | null"
    },
    "delivery": {
      "available": "boolean | null",
      "estimated_at": "ISO-8601-datetime | null",
      "notes": "string | null"
    },
    "quote_valid_until": "ISO-8601-datetime | null",
    "unclear_fields": ["field.path"],
    "completion_confidence": "number | null",
    "notes": "string | null"
  }
}
```

For `no_answer` or `failed`, `quote` is `null`; the attempt carries the terminal outcome and sanitized error information. A nullable value and an explicit `unclear` enum are distinct from a negative assertion.

### B. Reservation result

```json
{
  "schema_version": "1.0",
  "call_attempt_id": "uuid",
  "outcome": "confirmed | refused | unavailable | unclear | no_answer | failed",
  "supplier_reservation_reference": "string | null",
  "unclear_fields": ["field.path"],
  "notes": "string | null"
}
```

`supplier_reservation_reference` may be stored only when provided and is expected primarily for `confirmed`. `pending_approval` and `calling` are internal workflow states, not terminal result payloads.

## 17. Quote Normalization

The Procurement Agent coordinates normalization after structured call results arrive. Normalization itself is a deterministic Python application service that:

- Parses money as decimal plus ISO currency without floating-point arithmetic.
- Preserves tax inclusion separately; it does not guess tax.
- Converts quantity to an integer only when stated clearly.
- Converts warranty to structured status/duration while retaining description.
- Converts pickup/delivery statements to timestamps using the call/request timezone and retains notes.
- Preserves the original provider-neutral structured result in restricted storage.
- Emits reason codes for missing, contradictory, or unclear fields.
- Never converts an unclear reference into a confirmed match.

Currency conversion is not an MVP capability. Quotes in a currency that cannot be directly compared to the request budget require human review. Exact tax/budget and quote-validity policies remain deferred.

## 18. Deterministic Ranking Engine

The Procurement Agent invokes the ranking engine after normalization and exposes its result for human selection. The ranking engine itself is a versioned deterministic Python pure function over a sourcing request and normalized quotes. It returns:

- classification per quote: `excluded`, `human_review`, or `valid`;
- machine-readable reason codes;
- a stable ordered list of valid quotes;
- an explanation of every factor used;
- a policy version for reproducibility.

Only four factor families are allowed: exact-reference match, deadline, price, and warranty. Supplier reliability is prohibited from MVP ranking.

**Excluded:** confirmed non-match, confirmed out of stock/insufficient quantity, or confirmed fulfilment after the required deadline.

**Human review:** unclear reference, availability, quantity, deadline, price/currency, tax treatment that prevents budget evaluation, contradictory important fields, or insufficient completion confidence. Reviewable quotes are visible but do not outrank valid quotes automatically.

**Valid ranking:** exact reference is confirmed, required quantity is available, the deadline is met, price/currency are comparable, and no critical field is unclear. The engine then compares the permitted factors using a stable, documented policy and stable tie-breaking.

Exact weights or precedence, tie policy, confidence threshold, and tax-inclusive budget rule are intentionally not locked here. They must be finalized and covered by table-driven tests before ranking implementation. An LLM must not select, score, or break ties.

## 19. Idempotency & Duplicate Prevention

- Quote logical key: `quote:{sourcing_request_id}:{supplier_id}`.
- Reservation logical key: `reservation:{sourcing_request_id}:{selected_quote_id}`.
- Each logical call has monotonically increasing `attempt_number`; only explicit retry commands increment it.
- Approval endpoints require a client idempotency key and preview version/hash.
- A database transaction plus unique constraints creates at most one initial attempt for a logical call.
- Workers atomically claim queued attempts and do nothing for terminal/already-started attempts.
- Provider call IDs are unique when present.
- Explicit retries are permitted only from eligible terminal attempts and receive their own audit/event history.
- Redis redelivery, browser resubmission, or repeated API requests cannot create a second provider call for the same attempt.

The POC must verify whether CALL-E accepts a provider-side idempotency key: **VERIFY DURING CALL-E POC**. Local protection remains mandatory regardless.

## 20. Webhook Processing

`POST /api/v1/webhooks/call-e` performs this sequence:

1. Read the raw body with a strict size limit.
2. Verify provider authenticity/signature before trusting fields.
3. Parse the provider event and resolve the attempt by provider call ID or safe correlation metadata.
4. Insert a unique provider event ID, or a deterministic payload hash fallback, into the deduplication record.
5. Return success without side effects when already processed.
6. Lock the attempt row and validate monotonic state transition.
7. Validate/map the terminal result contract, normalize/store a quote or reservation outcome, and write the allowed audit event.
8. Commit atomically, then trigger comparison refresh if quote results changed.

Unknown event types are logged safely and acknowledged or rejected according to verified provider retry semantics. Signature method, event identifier, timeout expectation, and response behavior are **VERIFY DURING CALL-E POC**.

## 21. Authentication & Authorization Boundary

The browser authenticates to SupplyScout, never to CALL-E. FastAPI derives the acting user from the authenticated server session/token and ignores client-supplied actor IDs.

Authorization checks require that the acting user owns the sourcing request, owns or may use each supplier, explicitly asserted authorization for the supplier number, and is acting on the current preview/selection. Quote and reservation approvals record actor, time, and preview version.

The hackathon may use a single-user access gate rather than enterprise identity or multi-tenancy. The exact SupplyScout session mechanism is deferred, but it must support a stable user identity for ownership and approval evidence. Webhooks use provider authentication, not user authentication.

## 22. Security & Privacy

- CALL-E API keys and provider authentication credentials exist only in Railway server/worker secrets.
- No CALL-E secret uses a `NEXT_PUBLIC_` variable or appears in browser bundles/responses.
- E.164 validation occurs when suppliers are registered and again before call execution.
- Ordinary API responses, logs, previews, and audit metadata use masked phone numbers.
- Full numbers are available only to the server-side call adapter and narrowly authorized supplier management operations.
- TLS is required for browser/API, worker/provider, and webhook traffic.
- Webhook authenticity and replay defenses are mandatory, subject to provider POC details.
- Logs redact authorization headers, API keys, phone numbers, raw webhook bodies, and unnecessary conversation content.
- No payment data is collected, stored, or spoken; no code path authorizes purchase.
- Supplier refusal/end-of-conversation and uncertain outcomes are preserved.
- Data collection is limited to the structured procurement and reservation fields required by `MVP.md`.

## 23. Audit Trail

Only these event types are persisted:

- `sourcing_request.created`
- `call_preview.generated`
- `quote_calls.approved`
- `supplier_call.started`, `.completed`, or `.failed`
- `structured_quote.stored`
- `recommendation.generated`
- `offer.selected`
- `reservation.approved`
- `reservation_call.started`, `.completed`, or `.failed`
- `reservation_outcome.stored`

Events are append-only application records containing timestamp, actor/system source, request/entity identifiers, and minimal redacted metadata. They are not a full event-sourcing system and do not become an analytics suite. Retention duration and exact metadata fields remain deferred.

## 24. Error Handling & Retry Strategy

- Pydantic validation failures return structured `4xx` errors with field-safe messages.
- Invalid workflow transitions return `409 Conflict` and the current authoritative state.
- Missing ownership/authorization returns non-revealing `403`/`404` behavior.
- Queue or database failures do not claim that a call started.
- Provider timeouts/temporary errors may receive a small bounded automatic transport retry only when it is provably safe from duplicate call creation.
- If provider-side idempotency cannot be verified, ambiguous start-call failures are marked for human review instead of automatically redialed.
- No-answer and provider terminal failures require an explicit user retry to create another tracked attempt.
- Malformed structured results are retained in restricted diagnostic form, classified for human review/failed processing, and never ranked as valid.
- Webhook retries are safe because processing is idempotent.

Exact automatic retry counts/backoff and ambiguous CALL-E failure semantics are **VERIFY DURING CALL-E POC** and otherwise deferred.

## 25. Dry-Run / Fake Provider Strategy

Preview generation never calls a provider. It renders the intended supplier, disclosed AI identity, sourcing facts, requested quote fields, and safety limitations from current data.

`FakeCallProvider` implements the same adapter interface and asynchronous queue path as CALL-E. Deterministic fixtures cover the fixed demo suppliers A/B/C plus confirmed, refused, unavailable, unclear, no-answer, failed, malformed, duplicated-webhook, and delayed-result cases. It emits provider-neutral events through the same webhook/application ingestion service, without network calls or real numbers.

Real provider mode requires an explicit server configuration and authorized test numbers. Automated tests always default to fake mode.

## 26. Testing Strategy

- **Unit tests:** E.164 validation/masking, state transitions, normalization, eligibility, deterministic ranking, reason generation, idempotency keys.
- **Contract tests:** Pydantic REST models and both structured result schemas, including nullable/unclear fields.
- **Application tests:** approval gates, stale preview rejection, ownership, selection, reservation approval, audit emission, and LangGraph pause/resume checkpoints.
- **AI-boundary tests:** LangChain structured-output adapters, retrieval source filtering, and proof that retrieved context cannot overwrite CALL-E facts or enter deterministic ranking as an extra factor.
- **Worker tests:** repeated jobs, concurrent attempts, explicit retries, provider failures.
- **Webhook tests:** signature/authentication adapter, duplicate/out-of-order events, terminal monotonicity, malformed results.
- **Integration tests:** FastAPI + PostgreSQL + Redis + fake provider across the full workflow.
- **Frontend tests:** form validation, preview/approval separation, progress rendering, explanation, masking, reservation approval.
- **End-to-end demo test:** one request, three approved supplier attempts, terminal outcomes, at least one valid quote, recommendation, manual selection, separate reservation approval, and stored terminal reservation outcome.
- **CALL-E POC tests:** one authorized quote test call and one authorized reservation test call validating every item marked `VERIFY DURING CALL-E POC` before relying on real mode.

No test may dial an unapproved number. Real-call tests are opt-in and isolated from the default suite.

## 27. Observability / Logging

Use structured JSON logs from API and worker with request ID, sourcing request ID, call attempt ID, job ID, provider call ID when safe, state transition, latency, and sanitized error code. Never log secrets or full phone numbers.

Minimum operational views come from Railway/Vercel logs and database state; no large analytics stack is introduced. Track queue depth, failed jobs, webhook failures, calls by terminal state, and time from approval to terminal result. A correlation ID follows approval → job → provider → webhook.

The user-facing progress endpoint reads durable state, not logs.

## 28. Deployment Architecture

- **Vercel:** one Next.js frontend deployment.
- **Railway web process:** one FastAPI deployment with public REST and webhook routes.
- **Railway worker process:** one RQ worker from the shared backend artifact.
- **Managed PostgreSQL with pgvector:** authoritative relational data, LangGraph checkpoints, and limited curated RAG context.
- **Managed Redis:** RQ queues and short-lived coordination only.
- **CALL-E:** external calling provider reached only from Railway; webhook returns to Railway over HTTPS.

Deployments may scale to a small number of API/worker instances, but the MVP does not require high availability or autoscaling complexity. Database constraints, not single-process assumptions, enforce correctness.

## 29. Environment Variables / Secrets

Server/API/worker configuration:

- `DATABASE_URL`
- `REDIS_URL`
- `CALL_PROVIDER_MODE=fake|call_e`
- `CALL_E_API_KEY`
- `CALL_E_BASE_URL`
- `CALL_E_WEBHOOK_SECRET` if supported — **VERIFY DURING CALL-E POC**
- `CALL_E_WEBHOOK_URL`
- `APP_BASE_URL`
- `CORS_ALLOWED_ORIGINS`
- `SESSION_SECRET` or equivalent after auth choice
- worker concurrency and safe timeout settings

Any future model/embedding provider credentials used through LangChain must also be server-only secrets. The exact provider and variable names are deferred; none may be exposed through `NEXT_PUBLIC_` configuration.

Frontend-safe configuration may include only `NEXT_PUBLIC_API_BASE_URL`. Provider keys, database URLs, Redis URLs, webhook secrets, and session secrets must never be exposed as public variables. Startup validation fails closed when real-provider mode lacks required secrets.

## 30. MVP Performance & Scale Assumptions

These are design assumptions, not product expansion or performance promises:

- The required demo creates one request and attempts three approved suppliers.
- A sourcing request normally has a small supplier set; concurrency is bounded by worker configuration and verified provider limits.
- Call duration dominates application latency, so asynchronous status visibility matters more than low-millisecond API responses.
- PostgreSQL and one Redis queue are sufficient for hackathon traffic.
- The pgvector corpus is intentionally small and curated; it does not require a separate vector database or independent retrieval service.
- Short frontend polling is sufficient; WebSockets are unnecessary.
- A single API process and a small worker pool are acceptable initially.
- Retained data volume is small, but indexes cover request ownership, logical keys, provider call IDs, statuses, and timestamps.

## 31. Architecture Decisions

| Decision | Locked rationale |
| --- | --- |
| Modular monolith | Smallest maintainable unit for the hackathon; API and worker share domain rules |
| One server-side Procurement Agent | Orchestrates the complete sourcing workflow inside FastAPI/worker; no agent microservice or multi-agent system |
| LangGraph orchestration | Resumable workflow and explicit human-in-the-loop checkpoints without replacing PostgreSQL truth |
| LangChain utilities only | Model, prompt/context, structured-output, and retrieval support without business-state or ranking authority |
| REST, not GraphQL | Minimal explicit workflow commands and reads |
| PostgreSQL with pgvector as source of truth | Transactions protect workflow truth; pgvector adds only a small curated RAG layer |
| Redis + RQ worker | Lightweight asynchronous execution for parallel supplier calls |
| Server-side CALL-E Developer API adapter | Protects credentials and supports metadata, schemas, async execution, and webhooks subject to POC |
| Provider-neutral result contracts | Prevents provider details from contaminating domain/UI logic |
| Polling for progress | Simple and adequate for call-duration workflows |
| Versioned preview approvals | Proves exactly what the user approved and rejects stale data |
| Database-enforced logical calls and tracked attempts | Prevents accidental duplicate calls while preserving explicit retries |
| Deterministic ranking service | Reproducible explanations; no LLM winner selection |
| Fake adapter through the real job/result path | Safe local work and representative automated tests |
| Minimal append-only audit records | Proves the locked workflow without event sourcing or analytics scope |

## 32. Deferred Decisions

Deferred to the CALL-E POC:

- Exact API/SDK endpoint and authentication mechanics.
- Direct structured-schema support and result retrieval method.
- Webhook availability, signatures, identifiers, delivery/retry ordering, and payload mappings.
- Provider idempotency, metadata, concurrency, timeout, and error semantics.
- Provider completion-confidence support.

Deferred until architecture approval or implementation design:

- Exact model and embedding providers used through LangChain.
- Curated RAG ingestion/versioning procedure and retrieval limits.
- Detailed LangGraph checkpoint schema and checkpoint cleanup policy.
- Exact ranking precedence/weights, stable tie policy, and policy version `1` rules.
- Completion-confidence threshold.
- Tax-inclusive maximum-budget handling and quote-validity policy.
- Exact SupplyScout session/auth mechanism for the single-user hackathon context.
- Bounded transport retry counts and backoff after POC evidence.
- Audit metadata fields and retention duration.
- Whether full phone numbers require application-level encryption beyond managed-database encryption.

None of these deferrals permits supplier reliability, autonomous purchasing, payment handling, supplier discovery, or another vertical to enter the MVP.

## 33. Eraser Diagram Requirements

The architecture diagram set contains exactly three diagrams. Diagram 1 is completed/exported; Diagrams 2 and 3 remain pending and must not be created until requested.

### 1. High-Level System Architecture — Completed/Exported

The canonical implemented/exported high-level architecture diagram is stored at `docs/diagrams/supplyscout-high-level-architecture.png`.

- **Components:** user/browser, Next.js on Vercel, FastAPI boundary, SupplyScout Procurement Agent with LangGraph, LangChain utilities, deterministic ranking, PostgreSQL with pgvector, Redis/RQ, Python workers, server-side CALL-E adapter, CALL-E runtime, approved suppliers, webhook processing, and fake provider.
- **Relationships:** browser → frontend → API; API/agent ↔ PostgreSQL checkpoints and data; agent → curated RAG context; agent → Redis/RQ → workers; workers → adapter → CALL-E → suppliers; CALL-E → idempotent webhook/API; fake provider substitutes behind the same call contract.
- **Important labels:** human quote and reservation approvals, “LangGraph orchestrates—not business truth,” “RAG context only,” “LLM never chooses winner,” “server-side credentials,” “async calls,” and “idempotent webhook.”
- **Judge message:** one human-controlled Procurement Agent orchestrates context, parallel CALL-E conversations, deterministic comparison, and reservation while authoritative data and decisions remain constrained and explainable.

### 2. End-to-End CALL-E Sequence Diagram — Pending

- **Participants:** user, Next.js, FastAPI, PostgreSQL, Redis/worker, CALL-E, supplier.
- **Relationships/sequence:** create request → select approved suppliers → generate preview → approve → persist attempts → enqueue parallel jobs → CALL-E quote calls → idempotent terminal webhooks → normalize/rank → user selection → reservation preview → separate approval → reservation call → stored terminal outcome.
- **Important labels:** approval gates, three calls in parallel, AI disclosure, logical idempotency keys, uncertain result handling, deterministic recommendation, manual selection, and separate reservation authority.
- **Judge message:** several unstructured calls become comparable quotes and a completed reservation without surrendering human control.

### 3. Database ERD — Pending

- **Entities:** `Supplier`, `SourcingRequest`, supplier-selection join table, `CallAttempt`, `SupplierQuote`, `Reservation`, `AuditEvent`, and the internal webhook-deduplication record.
- **Relationships:** request-to-selected-suppliers many-to-many; request/supplier-to-attempts; completed quote attempt-to-quote zero-or-one; request-to-quotes one-to-many; request-to-selected quote zero-or-one; selected quote-to-reservation; reservation-to-attempts one-to-many; request-to-audit events one-to-many.
- **Important labels:** E.164 and authorization, quote/reservation logical keys, attempt numbers, unique provider IDs, terminal states, result classification, separate reservation approval, and redacted audit metadata.
- **Judge message:** a compact relational model makes approvals, duplicates, uncertain quotes, explanations, and reservation outcomes traceable and enforceable.
