from datetime import datetime, timezone
from uuid import uuid4

from fastapi import APIRouter, HTTPException, status

from ..agent.graph import ProcurementAgent
from ..agent.nodes import AgentDependencies
from ..agent.state import ProcurementAgentState
from ..config import settings
from ..db.models import SourcingRequest, Supplier, SupplierQuote
from ..domain.ranking import rank_quotes
from ..providers.calls.fake import FakeCallProvider
from ..schemas.quotes import (
    QuoteSelection,
    RankingEntry,
    RankingResponse,
    SupplierQuoteRead,
)
from ..schemas.sourcing import SourcingRequestCreate, SourcingRequestRead


router = APIRouter()
provider = FakeCallProvider()
suppliers: dict[str, Supplier] = {
    supplier.id: supplier for supplier in provider.suppliers()
}
sourcing_requests: dict[str, SourcingRequest] = {}
quotes_by_request: dict[str, list[SupplierQuote]] = {}
workflow_states: dict[str, ProcurementAgentState] = {}
agent = ProcurementAgent(
    AgentDependencies(
        sourcing_requests=sourcing_requests,
        suppliers=suppliers,
        quotes_by_request=quotes_by_request,
        provider=provider,
    )
)


@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok", "call_provider_mode": settings.call_provider_mode}


@router.post(
    "/api/v1/sourcing-requests",
    response_model=SourcingRequestRead,
    status_code=status.HTTP_201_CREATED,
)
def create_sourcing_request(payload: SourcingRequestCreate) -> SourcingRequest:
    now = datetime.now(timezone.utc)
    sourcing_request = SourcingRequest(
        id=str(uuid4()),
        status="draft",
        created_at=now,
        updated_at=now,
        **payload.model_dump(),
    )
    sourcing_requests[sourcing_request.id] = sourcing_request
    workflow_states[sourcing_request.id] = agent.initial_state(sourcing_request.id)
    return sourcing_request


@router.post("/api/v1/sourcing-requests/{request_id}/quote-preview")
def create_quote_preview(request_id: str) -> ProcurementAgentState:
    _get_request(request_id)
    state = _get_workflow(request_id)
    if state["workflow_status"] == "request_created":
        state = agent.run(state)
        workflow_states[request_id] = state
    return state


@router.post(
    "/api/v1/sourcing-requests/{request_id}/approve-quote-calls",
    response_model=list[SupplierQuoteRead],
)
def approve_quote_calls(request_id: str) -> list[SupplierQuoteRead]:
    sourcing_request = _get_request(request_id)
    if settings.call_provider_mode != "fake":
        raise HTTPException(status_code=503, detail="Only the fake call provider is enabled")
    state = _get_workflow(request_id)
    if state["workflow_status"] == "request_created":
        state = agent.run(state)
    if state["workflow_status"] == "awaiting_quote_approval":
        state = agent.run({**state, "quote_call_approved": True})
        workflow_states[request_id] = state
        sourcing_request.updated_at = datetime.now(timezone.utc)
    elif request_id not in quotes_by_request:
        raise HTTPException(status_code=409, detail="Quote calls cannot be approved now")
    return [_quote_response(quote) for quote in quotes_by_request[request_id]]


@router.get(
    "/api/v1/sourcing-requests/{request_id}/quotes",
    response_model=list[SupplierQuoteRead],
)
def get_quotes(request_id: str) -> list[SupplierQuoteRead]:
    _get_request(request_id)
    return [_quote_response(quote) for quote in quotes_by_request.get(request_id, [])]


@router.get(
    "/api/v1/sourcing-requests/{request_id}/ranking",
    response_model=RankingResponse,
)
def get_ranking(request_id: str) -> RankingResponse:
    sourcing_request = _get_request(request_id)
    quotes = quotes_by_request.get(request_id, [])
    if not quotes:
        raise HTTPException(status_code=409, detail="Quotes are not ready")
    ranked = rank_quotes(sourcing_request, quotes, suppliers)
    winner = ranked[0]
    return RankingResponse(
        sourcing_request_id=request_id,
        recommended_supplier_id=winner.supplier.id,
        recommended_supplier_name=winner.supplier.name,
        explanation=(
            f"{winner.supplier.name} is recommended because it confirms the exact "
            "reference and meets the required deadline."
        ),
        ranking=[
            RankingEntry(
                rank=index,
                quote_id=item.quote.id,
                supplier_id=item.supplier.id,
                supplier_name=item.supplier.name,
                reasons=item.reasons,
            )
            for index, item in enumerate(ranked, start=1)
        ],
    )


@router.post("/api/v1/sourcing-requests/{request_id}/select-quote")
def select_quote(
    request_id: str, payload: QuoteSelection
) -> ProcurementAgentState:
    _get_request(request_id)
    state = _get_workflow(request_id)
    if state["workflow_status"] != "awaiting_human_selection":
        raise HTTPException(status_code=409, detail="Quote selection is not available")
    quote_ids = {quote.id for quote in quotes_by_request.get(request_id, [])}
    if payload.quote_id not in quote_ids:
        raise HTTPException(status_code=404, detail="Quote not found")
    state = agent.run({**state, "selected_quote_id": payload.quote_id})
    workflow_states[request_id] = state
    return state


@router.post("/api/v1/sourcing-requests/{request_id}/reservation-preview")
def create_reservation_preview(request_id: str) -> ProcurementAgentState:
    _get_request(request_id)
    state = _get_workflow(request_id)
    if not state["selected_quote_id"]:
        raise HTTPException(status_code=409, detail="Explicit quote selection is required")
    if state["workflow_status"] == "awaiting_human_selection":
        state = agent.run(state)
        workflow_states[request_id] = state
    if state["workflow_status"] != "awaiting_reservation_approval":
        raise HTTPException(status_code=409, detail="Reservation preview is not available")
    return state


@router.post("/api/v1/sourcing-requests/{request_id}/approve-reservation")
def approve_reservation(request_id: str) -> ProcurementAgentState:
    _get_request(request_id)
    state = _get_workflow(request_id)
    if state["workflow_status"] != "awaiting_reservation_approval":
        raise HTTPException(status_code=409, detail="Reservation approval is not available")
    state = agent.run({**state, "reservation_approved": True})
    workflow_states[request_id] = state
    return state


@router.get("/api/v1/sourcing-requests/{request_id}/workflow")
def get_workflow(request_id: str) -> ProcurementAgentState:
    _get_request(request_id)
    return _get_workflow(request_id)


def _get_request(request_id: str) -> SourcingRequest:
    sourcing_request = sourcing_requests.get(request_id)
    if sourcing_request is None:
        raise HTTPException(status_code=404, detail="Sourcing request not found")
    return sourcing_request


def _get_workflow(request_id: str) -> ProcurementAgentState:
    state = workflow_states.get(request_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Workflow not found")
    return state


def _quote_response(quote: SupplierQuote) -> SupplierQuoteRead:
    return SupplierQuoteRead(
        id=quote.id,
        sourcing_request_id=quote.sourcing_request_id,
        supplier_id=quote.supplier_id,
        supplier_name=suppliers[quote.supplier_id].name,
        exact_reference_confirmed=quote.exact_reference_confirmed,
        offered_reference=quote.offered_reference,
        in_stock=quote.in_stock,
        manufacturer_or_brand=quote.manufacturer_or_brand,
        condition=quote.condition,
        quantity_available=quote.quantity_available,
        unit_price=quote.unit_price,
        currency=quote.currency,
        tax_included=quote.tax_included,
        warranty_months=quote.warranty_months,
        pickup_available_today=quote.pickup_available_today,
        delivery_eta=quote.delivery_eta,
        quote_valid_until=quote.quote_valid_until,
        supplier_notes=quote.supplier_notes,
        created_at=quote.created_at,
    )
