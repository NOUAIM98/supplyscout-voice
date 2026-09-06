from dataclasses import dataclass
from uuid import uuid4

from sqlalchemy.orm import Session

from ..db.models import CallAttempt, Reservation, SourcingRequest, SupplierQuote
from ..db.repositories import AuditRepository, CallAttemptRepository, QuoteRepository
from ..db.repositories import ReservationRepository, SourcingRequestRepository
from ..db.repositories import SupplierRepository
from ..domain.ranking import rank_quotes
from ..providers.calls.base import CallProvider
from ..knowledge.service import build_retriever, compose_quote_context, load_context
from .state import ProcurementAgentState


@dataclass
class AgentDependencies:
    session: Session
    provider: CallProvider


class ProcurementNodes:
    def __init__(self, dependencies: AgentDependencies) -> None:
        self.dependencies = dependencies
        self.requests = SourcingRequestRepository(dependencies.session)
        self.suppliers = SupplierRepository(dependencies.session)
        self.quotes = QuoteRepository(dependencies.session)
        self.reservations = ReservationRepository(dependencies.session)
        self.attempts = CallAttemptRepository(dependencies.session)
        self.audit = AuditRepository(dependencies.session)

    def context_retrieval(self, state: ProcurementAgentState) -> dict:
        request = self._request(state)
        retriever = build_retriever(self.dependencies.session)
        chunks = retriever.retrieve(request) if retriever else []
        request.knowledge_chunk_ids = [chunk.id for chunk in chunks]
        request.status = "context_retrieval"
        self.audit.record(request.id, "knowledge_retrieved", {"chunk_count": len(chunks)})
        return {"workflow_status": "context_retrieval", "knowledge_chunk_ids": request.knowledge_chunk_ids}

    def call_preview(self, state: ProcurementAgentState) -> dict:
        request = self._request(state)
        request.status = "call_preview"
        self.audit.record(request.id, "preview_generated", {"knowledge_chunk_ids": request.knowledge_chunk_ids})
        return {"workflow_status": "call_preview"}

    def awaiting_quote_approval(self, state: ProcurementAgentState) -> dict:
        self._request(state).status = "awaiting_quote_approval"
        return {"workflow_status": "awaiting_quote_approval"}

    def dispatch_supplier_calls(self, state: ProcurementAgentState) -> dict:
        if not state["quote_call_approved"]:
            return {
                "workflow_status": "awaiting_quote_approval",
                "errors": ["Explicit quote-call approval is required."],
            }
        request = self._request(state)
        self.audit.record(request.id, "quote_calls_approved")
        stored_quotes = []
        for supplier in self.suppliers.assigned_to(request.id):
            key = f"supplyscout:quote:{request.id}:{supplier.id}"
            attempt = CallAttempt(
                id=str(uuid4()), sourcing_request_id=request.id, supplier_id=supplier.id,
                call_type="quote", logical_idempotency_key=key, attempt_number=1,
                status="started",
            )
            self.attempts.add(attempt)
            self.audit.record(request.id, "supplier_call_started", {"supplier_id": supplier.id})
            context = compose_quote_context(load_context(self.dependencies.session, request.knowledge_chunk_ids))
            quote = self.dependencies.provider.create_quote_call(request, supplier, knowledge_context=context)
            stored_quotes.append(self.quotes.add(quote))
            attempt.status = "completed"
            self.audit.record(request.id, "supplier_call_completed", {"supplier_id": supplier.id})
            self.audit.record(request.id, "structured_quote_stored", {"quote_id": quote.id})
        request.status = "supplier_calls_dispatched"
        return {
            "workflow_status": "supplier_calls_dispatched",
            "quotes": [quote.id for quote in stored_quotes],
            "errors": [],
        }

    def normalize_quotes(self, state: ProcurementAgentState) -> dict:
        request = self._request(state)
        request.status = "quotes_normalized"
        quotes = self.quotes.list_for_request(request.id)
        self.audit.record(request.id, "quotes_normalized", {"quote_count": len(quotes)})
        return {"workflow_status": "quotes_normalized", "quotes": [q.id for q in quotes]}

    def rank_quotes(self, state: ProcurementAgentState) -> dict:
        request = self._request(state)
        quotes = self.quotes.list_for_request(request.id)
        suppliers = {supplier.id: supplier for supplier in self.suppliers.assigned_to(request.id)}
        ranking = [item.quote.id for item in rank_quotes(request, quotes, suppliers)]
        request.status = "ranked"
        self.audit.record(request.id, "recommendation_generated", {"quote_id": ranking[0]})
        return {"workflow_status": "ranked", "ranking": ranking, "recommended_quote_id": ranking[0]}

    def awaiting_human_selection(self, state: ProcurementAgentState) -> dict:
        self._request(state).status = "awaiting_human_selection"
        return {"workflow_status": "awaiting_human_selection"}

    def reservation_preview(self, state: ProcurementAgentState) -> dict:
        if not state["selected_quote_id"]:
            return {"workflow_status": "awaiting_human_selection", "errors": ["Explicit supplier selection is required."]}
        request = self._request(state)
        quote = self.quotes.get(state["selected_quote_id"])
        if quote is None:
            return {"workflow_status": "awaiting_human_selection", "errors": ["Selected quote was not found."]}
        request.selected_quote_id = quote.id
        request.status = "reservation_preview"
        if self.reservations.for_request(request.id) is None:
            self.reservations.add(Reservation(
                id=str(uuid4()), sourcing_request_id=request.id, supplier_quote_id=quote.id,
                supplier_id=quote.supplier_id, status="pending_approval",
            ))
            self.audit.record(request.id, "offer_selected", {"quote_id": quote.id})
            self.audit.record(request.id, "reservation_preview_prepared")
        return {"workflow_status": "reservation_preview", "reservation_result": {"outcome": "pending_approval", "supplier_reference": None}, "errors": []}

    def awaiting_reservation_approval(self, state: ProcurementAgentState) -> dict:
        self._request(state).status = "awaiting_reservation_approval"
        return {"workflow_status": "awaiting_reservation_approval"}

    def reservation_call(self, state: ProcurementAgentState) -> dict:
        if not state["reservation_approved"]:
            return {"workflow_status": "awaiting_reservation_approval", "errors": ["Explicit reservation approval is required."]}
        request = self._request(state)
        quote = self._selected_quote(state)
        supplier = {s.id: s for s in self.suppliers.assigned_to(request.id)}[quote.supplier_id]
        reservation = self.reservations.for_request(request.id)
        if reservation is None:
            raise RuntimeError("Reservation preview is required")
        self.audit.record(request.id, "reservation_approved")
        self.audit.record(request.id, "reservation_call_started")
        attempt = CallAttempt(
            id=str(uuid4()), sourcing_request_id=request.id, supplier_id=supplier.id,
            call_type="reservation",
            logical_idempotency_key=f"supplyscout:reservation:{request.id}:{quote.id}",
            attempt_number=1, status="started",
        )
        self.attempts.add(attempt)
        result = self.dependencies.provider.create_reservation_call(
            request, quote, supplier, approved=True
        )
        attempt.status = "completed"
        reservation.status = str(result["outcome"])
        reservation.reservation_reference = result["supplier_reference"]
        request.status = "reservation_call"
        self.audit.record(request.id, "reservation_call_completed")
        self.audit.record(request.id, "reservation_outcome_stored", {"outcome": reservation.status})
        return {"workflow_status": "reservation_call", "reservation_result": result, "errors": []}

    def completed(self, state: ProcurementAgentState) -> dict:
        request = self._request(state)
        request.status = "completed"
        self.audit.record(request.id, "workflow_completed")
        return {"workflow_status": "completed"}

    def _request(self, state: ProcurementAgentState) -> SourcingRequest:
        request = self.requests.get(state["sourcing_request_id"])
        if request is None:
            raise KeyError(state["sourcing_request_id"])
        return request

    def _selected_quote(self, state: ProcurementAgentState) -> SupplierQuote:
        quote = self.quotes.get(str(state["selected_quote_id"]))
        if quote is None:
            raise KeyError(state["selected_quote_id"])
        return quote
