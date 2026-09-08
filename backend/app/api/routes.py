from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..agent.graph import ProcurementAgent
from ..agent.nodes import AgentDependencies
from ..agent.state import ProcurementAgentState
from ..config import settings
from ..db.models import SourcingRequest, Supplier, SupplierQuote
from ..db.repositories import AuditRepository, CallAttemptRepository, QuoteRepository, ReservationRepository
from ..db.repositories import SourcingRequestRepository, SupplierRepository
from ..db.session import get_db
from ..domain.ranking import rank_quotes
from ..knowledge.service import build_retriever, compose_quote_context, provenance
from ..providers.calls.factory import create_call_provider
from ..providers.calls.calle import CalleCallProvider, CalleResultError
from ..providers.calls.guard import LiveCallBlocked, assert_live_call_allowed
from ..schemas.quotes import QuoteSelection, RankingEntry, RankingResponse, SupplierQuoteRead
from ..schemas.sourcing import SourcingRequestCreate, SourcingRequestRead


router = APIRouter()
provider = create_call_provider(settings)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "call_provider_mode": settings.call_provider_mode}


@router.post(
    "/api/v1/sourcing-requests", response_model=SourcingRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_sourcing_request(
    payload: SourcingRequestCreate, session: Session = Depends(get_db)
) -> SourcingRequest:
    requests = SourcingRequestRepository(session)
    suppliers = SupplierRepository(session)
    request = requests.add(SourcingRequest(
        id=str(uuid4()), status="request_created", **payload.model_dump()
    ))
    available_suppliers = (
        provider.suppliers()
        if provider.mode == "fake"
        else [
            supplier for supplier in suppliers.all()
            if supplier.authorized_for_calls
            and supplier.phone_e164 in settings.allowed_calle_recipients
        ]
    )
    for supplier in available_suppliers:
        stored = suppliers.add(supplier)
        session.flush()
        requests.assign_supplier(request.id, stored.id)
    AuditRepository(session).record(request.id, "request_created")
    session.flush()
    return request


@router.get(
    "/api/v1/sourcing-requests/{request_id}", response_model=SourcingRequestRead
)
def get_sourcing_request(
    request_id: str, session: Session = Depends(get_db)
) -> SourcingRequest:
    return _get_request(session, request_id)


@router.post("/api/v1/sourcing-requests/{request_id}/quote-preview")
def create_quote_preview(
    request_id: str, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    request = _get_request(session, request_id)
    state = _workflow_state(session, request)
    if state["workflow_status"] == "request_created":
        state = _agent(session).run(state)
    return state


@router.post("/api/v1/sourcing-requests/{request_id}/context-preview")
def context_preview(request_id: str, session: Session = Depends(get_db)) -> dict:
    request = _get_request(session, request_id)
    try:
        retriever = build_retriever(session)
    except ValueError:
        raise HTTPException(status_code=503, detail="RAG configuration is not ready") from None
    chunks = retriever.retrieve(request) if retriever else []
    return {"mode": settings.rag_mode, "chunks": provenance(chunks),
            "task_context": compose_quote_context(chunks), "call_started": False}


@router.post(
    "/api/v1/sourcing-requests/{request_id}/approve-quote-calls",
    response_model=list[SupplierQuoteRead],
)
def approve_quote_calls(
    request_id: str, session: Session = Depends(get_db)
) -> list[SupplierQuoteRead]:
    request = _get_request(session, request_id)
    state = _workflow_state(session, request)
    if state["workflow_status"] == "request_created":
        state = _agent(session).run(state)
    if state["workflow_status"] == "awaiting_quote_approval":
        if provider.mode == "calle":
            audit = AuditRepository(session)
            if not audit.exists(request.id, "quote_calls_approved"):
                audit.record(request.id, "quote_calls_approved")
            session.flush()
            try:
                for supplier in SupplierRepository(session).assigned_to(request.id):
                    assert_live_call_allowed(session, settings, request, supplier, "quote")
            except LiveCallBlocked as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from None
        try:
            _agent(session).run({**state, "quote_call_approved": True})
        except LiveCallBlocked as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
        request.updated_at = datetime.now(timezone.utc)
        session.flush()
    elif not QuoteRepository(session).list_for_request(request_id):
        raise HTTPException(status_code=409, detail="Quote calls cannot be approved now")
    return _quote_responses(session, request_id)


@router.get(
    "/api/v1/sourcing-requests/{request_id}/quotes",
    response_model=list[SupplierQuoteRead],
)
def get_quotes(
    request_id: str, session: Session = Depends(get_db)
) -> list[SupplierQuoteRead]:
    _get_request(session, request_id)
    return _quote_responses(session, request_id)


@router.get(
    "/api/v1/sourcing-requests/{request_id}/ranking", response_model=RankingResponse
)
def get_ranking(request_id: str, session: Session = Depends(get_db)) -> RankingResponse:
    request = _get_request(session, request_id)
    quotes = QuoteRepository(session).list_for_request(request_id)
    if not quotes:
        raise HTTPException(status_code=409, detail="Quotes are not ready")
    suppliers = {s.id: s for s in SupplierRepository(session).assigned_to(request_id)}
    ranked = rank_quotes(request, quotes, suppliers)
    winner = ranked[0]
    return RankingResponse(
        sourcing_request_id=request_id,
        recommended_supplier_id=winner.supplier.id,
        recommended_supplier_name=winner.supplier.name,
        explanation=f"{winner.supplier.name} is recommended because it confirms the exact reference and meets the required deadline.",
        ranking=[RankingEntry(
            rank=index, quote_id=item.quote.id, supplier_id=item.supplier.id,
            supplier_name=item.supplier.name, reasons=item.reasons,
        ) for index, item in enumerate(ranked, start=1)],
    )


@router.post("/api/v1/sourcing-requests/{request_id}/select-quote")
def select_quote(
    request_id: str, payload: QuoteSelection, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    request = _get_request(session, request_id)
    state = _workflow_state(session, request)
    if state["workflow_status"] != "awaiting_human_selection":
        raise HTTPException(status_code=409, detail="Quote selection is not available")
    quote = QuoteRepository(session).get(payload.quote_id)
    if quote is None or quote.sourcing_request_id != request_id:
        raise HTTPException(status_code=404, detail="Quote not found")
    request.selected_quote_id = quote.id
    session.flush()
    return _agent(session).run({**state, "selected_quote_id": quote.id})


@router.post("/api/v1/sourcing-requests/{request_id}/reservation-preview")
def create_reservation_preview(
    request_id: str, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    request = _get_request(session, request_id)
    state = _workflow_state(session, request)
    if not state["selected_quote_id"]:
        raise HTTPException(status_code=409, detail="Explicit quote selection is required")
    if state["workflow_status"] == "awaiting_human_selection":
        state = _agent(session).run(state)
    if state["workflow_status"] != "awaiting_reservation_approval":
        raise HTTPException(status_code=409, detail="Reservation preview is not available")
    return state


@router.post("/api/v1/sourcing-requests/{request_id}/approve-reservation")
def approve_reservation(
    request_id: str, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    request = _get_request(session, request_id)
    state = _workflow_state(session, request)
    if state["workflow_status"] != "awaiting_reservation_approval":
        raise HTTPException(status_code=409, detail="Reservation approval is not available")
    if provider.mode == "calle":
        quote = QuoteRepository(session).get(str(request.selected_quote_id))
        if quote is None:
            raise HTTPException(status_code=409, detail="Selected quote is required")
        supplier = next((item for item in SupplierRepository(session).assigned_to(request.id) if item.id == quote.supplier_id), None)
        if supplier is None:
            raise HTTPException(status_code=403, detail="Selected supplier is not assigned")
        audit = AuditRepository(session)
        if not audit.exists(request.id, "reservation_approved"):
            audit.record(request.id, "reservation_approved")
        session.flush()
        try:
            assert_live_call_allowed(session, settings, request, supplier, "reservation")
        except LiveCallBlocked as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from None
    try:
        return _agent(session).run({**state, "reservation_approved": True})
    except LiveCallBlocked as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from None


@router.get("/api/v1/sourcing-requests/{request_id}/workflow")
def get_workflow(
    request_id: str, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    return _workflow_state(session, _get_request(session, request_id))


@router.get("/api/v1/sourcing-requests/{request_id}/activity")
def get_activity(request_id: str, session: Session = Depends(get_db)) -> list[dict]:
    _get_request(session, request_id)
    return [
        {
            "id": event.id,
            "event_type": event.event_type,
            "created_at": event.created_at,
        }
        for event in AuditRepository(session).list_for_request(request_id)
    ]


@router.get("/api/v1/runtime")
def get_runtime() -> dict[str, str | bool]:
    return {
        "call_provider_mode": settings.call_provider_mode,
        "live_calls_enabled": settings.calle_live_enabled,
    }


@router.get("/api/v1/sourcing-requests/{request_id}/call-attempts")
def get_call_attempts(request_id: str, session: Session = Depends(get_db)) -> list[dict]:
    _get_request(session, request_id)
    return _attempt_responses(CallAttemptRepository(session).list_for_request(request_id))


@router.post("/api/v1/sourcing-requests/{request_id}/sync-calls")
def sync_calls(request_id: str, session: Session = Depends(get_db)) -> dict:
    request = _get_request(session, request_id)
    if not isinstance(provider, CalleCallProvider):
        raise HTTPException(status_code=409, detail="Call synchronization is only available in CALL-E mode")
    attempts_repo = CallAttemptRepository(session)
    quotes = QuoteRepository(session)
    reservations = ReservationRepository(session)
    audit = AuditRepository(session)
    suppliers = {item.id: item for item in SupplierRepository(session).assigned_to(request_id)}
    attempts = attempts_repo.list_for_request(request_id)
    for attempt in attempts:
        if attempt.status not in {"queued", "calling", "in_progress"} or not attempt.provider_call_id:
            continue
        try:
            response = provider.get_call(attempt.provider_call_id)
        except Exception:
            attempt.status = "failed"
            continue
        provider_status = _safe_provider_status(response)
        if provider_status in {"queued", "calling", "in_progress"}:
            attempt.status = provider_status
            continue
        if attempt.call_type == "quote":
            if provider_status == "completed":
                try:
                    quote = provider.normalize_quote_response(response, request, suppliers[attempt.supplier_id])
                    quotes.add(quote)
                    attempt.status = "completed"
                    audit.record(request_id, "call_completed", {"call_type": "quote"})
                    audit.record(request_id, "quote_normalized", {"quote_id": quote.id})
                except (CalleResultError, KeyError):
                    attempt.status = "failed"
            else:
                attempt.status = provider_status
        else:
            reservation = reservations.for_request(request_id)
            if reservation is None:
                attempt.status = "failed"
                continue
            result = provider.normalize_reservation_response(response) if provider_status == "completed" else {"outcome": provider_status, "supplier_reference": None}
            reservation.status = str(result["outcome"])
            reservation.reservation_reference = result["supplier_reference"]
            attempt.status = str(result["outcome"])
            request.status = "completed"
            audit.record(request_id, "reservation_completed", {"outcome": reservation.status})
            if not audit.exists(request_id, "workflow_completed"):
                audit.record(request_id, "workflow_completed")
    session.flush()
    quote_attempts = [item for item in attempts if item.call_type == "quote"]
    if quote_attempts and all(item.status not in {"queued", "calling", "in_progress"} for item in quote_attempts) and quotes.list_for_request(request_id) and request.status == "supplier_calls_dispatched":
        _agent(session).run(_workflow_state(session, request))
    return {
        "workflow": _workflow_state(session, request),
        "attempts": _attempt_responses(attempts),
    }


def _agent(session: Session) -> ProcurementAgent:
    return ProcurementAgent(AgentDependencies(session=session, provider=provider))


def _get_request(session: Session, request_id: str) -> SourcingRequest:
    request = SourcingRequestRepository(session).get(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="Sourcing request not found")
    return request


def _workflow_state(session: Session, request: SourcingRequest) -> ProcurementAgentState:
    quotes = QuoteRepository(session).list_for_request(request.id)
    suppliers = {s.id: s for s in SupplierRepository(session).assigned_to(request.id)}
    ranking = [item.quote.id for item in rank_quotes(request, quotes, suppliers)] if quotes else []
    reservation = ReservationRepository(session).for_request(request.id)
    return {
        "sourcing_request_id": request.id,
        "knowledge_chunk_ids": request.knowledge_chunk_ids,
        "workflow_status": request.status,
        "quote_call_approved": request.status not in {"request_created", "context_retrieval", "call_preview", "awaiting_quote_approval"},
        "quotes": [quote.id for quote in quotes],
        "ranking": ranking,
        "recommended_quote_id": ranking[0] if ranking else None,
        "selected_quote_id": request.selected_quote_id,
        "reservation_approved": reservation is not None and reservation.status != "pending_approval",
        "reservation_result": None if reservation is None else {
            "outcome": reservation.status,
            "supplier_reference": reservation.reservation_reference,
        },
        "errors": [],
    }


def _quote_responses(session: Session, request_id: str) -> list[SupplierQuoteRead]:
    suppliers = {s.id: s for s in SupplierRepository(session).assigned_to(request_id)}
    return [_quote_response(quote, suppliers) for quote in QuoteRepository(session).list_for_request(request_id)]


def _quote_response(
    quote: SupplierQuote, suppliers: dict[str, Supplier]
) -> SupplierQuoteRead:
    return SupplierQuoteRead(
        id=quote.id, sourcing_request_id=quote.sourcing_request_id,
        supplier_id=quote.supplier_id, supplier_name=suppliers[quote.supplier_id].name,
        exact_reference_confirmed=quote.exact_reference_confirmed,
        offered_reference=quote.offered_reference, in_stock=quote.in_stock,
        manufacturer_or_brand=quote.manufacturer_or_brand, condition=quote.condition,
        quantity_available=quote.quantity_available, unit_price=quote.unit_price,
        currency=quote.currency, tax_included=quote.tax_included,
        warranty_months=quote.warranty_months,
        pickup_available_today=quote.pickup_available_today,
        delivery_eta=quote.delivery_eta, quote_valid_until=quote.quote_valid_until,
        supplier_notes=quote.supplier_notes, created_at=quote.created_at,
    )


def _safe_provider_status(response: dict) -> str:
    value = response.get("status")
    if value in {"queued", "calling", "in_progress", "completed", "failed", "no_answer"}:
        return str(value)
    return "in_progress"


def _attempt_responses(attempts: list) -> list[dict]:
    return [
        {
            "id": attempt.id,
            "call_type": attempt.call_type,
            "status": attempt.status,
            "provider_call_id": attempt.provider_call_id,
        }
        for attempt in attempts
    ]
