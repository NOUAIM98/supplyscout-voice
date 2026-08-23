# SupplyScout Voice MVP Scope

## 1. Product Summary

SupplyScout Voice is a standalone AI-powered hackathon web application for **CALL-E: Your Code Is Calling**. It is built as an independent product and does not depend on any existing host product or business platform. CALL-E is its essential external calling integration: it makes real outbound phone calls to approved suppliers, turns supplier conversations into structured real-time quotes, and—after a separate user approval—calls the selected supplier to request a reservation.

The hackathon MVP serves one use case: **independent auto repair shops sourcing urgent automotive parts**.

Long-term concept: **A procurement agent for businesses whose supplier information still lives on the phone.**

The product is not merely “enter a phone number and let AI call.” Its value is converting several unstructured supplier conversations into structured procurement information and a completed, human-controlled sourcing workflow.

## 2. Hackathon Objective

Demonstrate one complete, reliable sourcing flow:

`1 sourcing request` → `approved supplier selection` → `call preview` → `explicit quote-call approval` → `multiple approved supplier calls` → `structured quote results` → `deterministic comparison` → `valid recommendation` → `human supplier selection` → `explicit reservation approval` → `reservation call` → `structured reservation outcome`

The priority is a working end-to-end flow, not a broad feature set or a polished dashboard without functional calling and reservation workflows.

## 3. Problem

Auto repair shops often need parts urgently, while supplier stock, price, warranty, and pickup or delivery information may not be reliably available online or through APIs. Employees must call multiple suppliers, repeat the same questions, take notes, compare incomplete answers, select an offer, and call the supplier back.

SupplyScout automates this phone-work while preserving human approval for real calls and supplier selection.

## 4. Target User

The primary MVP user is **an employee or owner of an independent auto repair shop sourcing an urgent automotive part**.

Other industries and user types are outside the MVP.

## 5. Value Proposition

SupplyScout helps the user:

- Contact multiple previously approved suppliers with a consistent request.
- Capture comparable quote data from phone conversations.
- Distinguish valid offers from uncertain or unusable results.
- Receive an explainable, deterministic recommendation.
- Retain final control over calls, supplier selection, and reservation.

## 6. Core User Journey

1. The user creates a sourcing request.
2. The user provides:
   - vehicle make
   - vehicle model
   - vehicle year
   - part name
   - exact/OEM reference, when available
   - quantity
   - maximum budget
   - required-by deadline
3. The user chooses suppliers that they manually registered or selected and are authorized to call.
4. SupplyScout generates a dry-run call preview.
5. The user explicitly approves the outbound calls.
6. CALL-E calls each approved supplier.
7. CALL-E clearly identifies itself as an AI assistant.
8. CALL-E attempts to collect all fields defined in [Structured Supplier Quote](#8-structured-supplier-quote).
9. CALL-E returns structured results.
10. SupplyScout stores and normalizes each quote.
11. SupplyScout clearly flags invalid or uncertain quotes.
12. SupplyScout compares valid offers using deterministic rules.
13. The user sees the recommendation and the reasons behind it.
14. The user manually selects an offer.
15. The user explicitly approves a separate reservation call.
16. CALL-E calls the selected supplier to request a reservation.
17. SupplyScout stores and displays the reservation outcome and any supplier reference.

## 7. MVP Features

The MVP includes only:

- Sourcing request creation
- Selection from previously approved suppliers
- Dry-run and call preview
- Explicit human approval before real quote calls
- CALL-E integration
- Multiple supplier calls
- Call status tracking
- Strict structured quote results
- Quote storage and normalization
- Invalid and uncertain quote handling
- Deterministic quote comparison
- Explainable recommendation
- Human offer selection
- Separate reservation approval
- Reservation phone call
- Structured reservation result
- Basic audit trail
- Phone-number masking
- Duplicate-call prevention through idempotency

**MVP supplier approval model**

- Suppliers are manually registered or selected by the user.
- A supplier phone number may be activated for outbound calls only when the user is authorized to call it.
- Hackathon live testing uses explicitly authorized test phone numbers.
- Supplier discovery is outside the MVP.

## 8. Structured Supplier Quote

For each supplier call, CALL-E attempts to return a structured result containing:

- Exact-reference confirmation: confirmed, not confirmed, or unclear
- Availability: in stock, unavailable, or unclear
- Condition
- Manufacturer or brand
- Quantity available
- Unit price
- Currency
- Whether tax is included
- Warranty
- Pickup availability
- Delivery estimate
- Quote validity

The stored result must preserve uncertainty rather than turning unclear responses into asserted facts. Normalization should make quotes comparable while retaining the supplier's original meaning and relevant call outcome. Missing, contradictory, or low-confidence information must be visibly flagged for human review.

## 9. Quote Evaluation Rules

Recommendation logic must be deterministic and explainable. It must not ask an LLM to arbitrarily choose a winner.

The initial MVP ranking may use only these factors:

1. Exact-reference match
2. Ability to meet the required-by deadline
3. Price, including its relationship to the maximum budget
4. Warranty

No trustworthy historical supplier reliability dataset exists for the MVP, so supplier reliability must not affect the initial ranking. The exact scoring or ordering must be documented when implemented so the same inputs produce the same outcome. The UI must show why an offer was included, excluded, sent for review, and recommended.

A quote must be excluded from valid ranking or require human review when appropriate, including when:

- The exact reference is not confirmed.
- The item is out of stock.
- Pickup or delivery misses the required deadline.
- Important fields are missing, contradictory, or unclear.
- Completion confidence is insufficient.

The recommendation is advisory. The user always makes the final supplier decision.

## 10. Reservation Workflow

Reservation is a separate, human-controlled stage:

1. The user reviews the normalized quotes and recommendation.
2. The user manually selects one offer.
3. SupplyScout shows a reservation call preview.
4. The user explicitly approves the reservation call.
5. CALL-E contacts only the selected supplier and requests a reservation.
6. SupplyScout records a structured outcome and any important uncertainty or refusal.

The minimum reservation outcome states are:

- `pending_approval`
- `calling`
- `confirmed`
- `refused`
- `unavailable`
- `unclear`
- `no_answer`
- `failed`

When the outcome is `confirmed`, SupplyScout stores a supplier reservation reference when the supplier provides one.

A quote-call approval does not authorize a reservation call. A reservation request does not authorize payment or purchase.

## 11. Safety & Human Approval

- Only supplier phone numbers manually registered or selected by the user and authorized for calling may be activated for outbound calls.
- Hackathon live testing must use explicitly authorized test phone numbers.
- Every real quote call requires explicit user approval.
- A reservation call requires a second, separate explicit approval.
- A dry-run/no-call path and call preview must be available.
- All authenticated CALL-E operations and credentials must remain server-side.
- The browser must never receive CALL-E API keys or provider authentication credentials.
- Phone numbers must use E.164 validation.
- Phone numbers must be masked in normal UI and log output where appropriate.
- A quote call is logically unique to a sourcing request and supplier.
- A reservation call is logically unique to a sourcing request and its selected quote.
- Explicit retries may create new tracked attempts, but accidental duplicate requests must not create duplicate calls.
- No payment information may be sent over calls.
- SupplyScout must never automatically purchase anything or spend money.
- SupplyScout and CALL-E must not claim an exact part match when uncertain.
- CALL-E must clearly identify itself as an AI assistant.
- Suppliers must be allowed to refuse or end the conversation.
- Important uncertain outcomes must be escalated for human review.
- The MVP audit trail is limited to the following events, recorded without exposing sensitive credentials or unnecessarily revealing phone numbers:
  - sourcing request created
  - call preview generated
  - quote calls approved
  - supplier call started, completed, or failed
  - structured quote stored
  - recommendation generated
  - offer selected
  - reservation approved
  - reservation call started, completed, or failed
  - reservation outcome stored

## 12. Non-Goals

The hackathon MVP does not include:

- Native Android or iOS applications
- Payments or credit card collection
- Autonomous purchasing or spending
- Complex negotiation
- Marketplace functionality
- Subscription or billing systems
- A full CRM
- A large analytics suite
- A generic AI chatbot
- Multi-industry support
- A large supplier discovery engine
- Complex multi-tenant enterprise functionality
- Inventory management
- Accounting functionality
- ERP replacement

These exclusions remain outside the MVP even if they are plausible future extensions.

## 13. Demo Scenario

Use this fixed reference scenario for the hackathon demo.

**Sourcing request**

- Vehicle: 2019 Renault Clio
- Part: Alternator
- Quantity: 1
- Maximum budget: €180
- Required: Today
- Reference: `TEST-ALT-CLIO-2019-001` — a clearly fictional, demo-only test reference, not a real OEM claim

**Example outcomes**

| Supplier | Exact reference | Availability | Price | Warranty | Fulfilment |
| --- | --- | --- | ---: | --- | --- |
| A | Confirmed | In stock | €145 | 12 months | Pickup today |
| B | Confirmed | Available | €132 | Not specified | Available tomorrow |
| C | Cannot be confirmed | Not specified | €118 | Not specified | Not specified |

**Expected application decision:** Supplier A ranks highest because it confirms the fictional test reference and meets the required deadline. Supplier B misses the deadline. Supplier C cannot confirm the test reference and therefore cannot outrank a valid confirmed offer.

The user manually selects the offer and explicitly approves a reservation call. The expected final state is a confirmed reservation with a supplier reference, or another clear structured reservation outcome if confirmation is not obtained.

## 14. MVP Success Criteria

The MVP is successful only when the complete reference flow works end to end:

`1 sourcing request` → `approved supplier selection` → `call preview` → `explicit quote-call approval` → `multiple approved supplier calls` → `structured quote results` → `deterministic comparison` → `valid recommendation` → `human supplier selection` → `explicit reservation approval` → `reservation call` → `structured reservation outcome`

Completion requires that:

- Calls target only user-selected, approved suppliers.
- The user previews and explicitly approves real quote calls.
- Multiple call outcomes are tracked and converted into strict structured results.
- Invalid and uncertain results are clearly distinguished from valid quotes.
- Valid quotes are compared with documented deterministic rules.
- The recommendation is explained to the user.
- The user, not the system, selects the supplier.
- The reservation call occurs only after a separate explicit approval.
- The reservation outcome and any reference are stored.
- Duplicate-call protections and a basic audit trail operate across the flow.

A beautiful dashboard without this working flow is not MVP completion.

**Minimum demo pass condition**

- One sourcing request is created.
- Three approved suppliers are attempted.
- Structured terminal call outcomes are produced for the attempts.
- At least one valid quote exists.
- SupplyScout generates an explainable deterministic comparison and recommendation.
- The user manually selects an offer.
- The user separately approves a reservation call.
- The reservation call returns and stores a structured terminal outcome.

## 15. Metrics to Measure

During later authorized real-world tests, measure without assuming values:

- Total sourcing time
- Number of suppliers contacted
- Call answer rate
- Number of valid quotes received
- Time to first valid quote
- Price difference between valid offers
- Sourcing requests successfully resolved
- Estimated employee time saved

Actual values must come from testing; they must not be invented.

## 16. Future Expansion — Brief Only

After the automotive-parts MVP is validated, the concept may be evaluated for other phone-dependent procurement workflows. Historical supplier reliability may also be considered only when a trustworthy dataset and an explicit evaluation policy exist. Any expansion requires separate scope decisions and must not broaden the hackathon MVP.

## 17. Open Questions / Assumptions

- **CALL-E contract:** Exact integration methods, event/status semantics, supported structured-output behavior, and call constraints are not established here and must be verified before architecture or implementation.
- **Scoring details:** The four initial ranking factors are fixed for MVP scope, but their precise weights, precedence, and handling of ties remain to be specified deterministically. These details must not introduce supplier reliability into the MVP.
- **Confidence threshold:** The threshold and evidence used to mark completion confidence as insufficient remain to be defined.
- **Quote validity:** The expected representation of a supplier's validity period and the behavior when none is provided remain to be defined.
- **Tax and budget:** Whether maximum budget comparisons use tax-inclusive totals when tax status varies or is unclear remains to be defined.
- **Audit retention:** Required audit fields and retention duration remain to be defined, subject to minimizing sensitive data.
