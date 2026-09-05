from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..agent.graph import ProcurementAgent
from ..agent.nodes import AgentDependencies
from ..agent.state import ProcurementAgentState
from ..config import settings
from ..db.models import SourcingRequest, Supplier, SupplierQuote
from ..db.repositories import AuditRepository, QuoteRepository, ReservationRepository
from ..db.repositories import SourcingRequestRepository, SupplierRepository
from ..db.session import get_db
from ..domain.ranking import rank_quotes
from ..providers.calls.factory import create_call_provider
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
    for supplier in provider.suppliers():
        stored = suppliers.add(supplier)
        session.flush()
        requests.assign_supplier(request.id, stored.id)
    AuditRepository(session).record(request.id, "request_created")
    session.flush()
    return request


@router.post("/api/v1/sourcing-requests/{request_id}/quote-preview")
def create_quote_preview(
    request_id: str, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    request = _get_request(session, request_id)
    state = _workflow_state(session, request)
    if state["workflow_status"] == "request_created":
        state = _agent(session).run(state)
    return state


@router.post(
    "/api/v1/sourcing-requests/{request_id}/approve-quote-calls",
    response_model=list[SupplierQuoteRead],
)
def approve_quote_calls(
    request_id: str, session: Session = Depends(get_db)
) -> list[SupplierQuoteRead]:
    request = _get_request(session, request_id)
    if settings.call_provider_mode != "fake":
        raise HTTPException(status_code=503, detail="Only the fake call provider is enabled")
    state = _workflow_state(session, request)
    if state["workflow_status"] == "request_created":
        state = _agent(session).run(state)
    if state["workflow_status"] == "awaiting_quote_approval":
        _agent(session).run({**state, "quote_call_approved": True})
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
    return _agent(session).run({**state, "reservation_approved": True})


@router.get("/api/v1/sourcing-requests/{request_id}/workflow")
def get_workflow(
    request_id: str, session: Session = Depends(get_db)
) -> ProcurementAgentState:
    return _workflow_state(session, _get_request(session, request_id))


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
        "workflow_status": request.status,
        "quote_call_approved": request.status not in {"request_created", "call_preview", "awaiting_quote_approval"},
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
