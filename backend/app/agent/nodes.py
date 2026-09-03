from dataclasses import dataclass

from ..db.models import SourcingRequest, Supplier, SupplierQuote
from ..domain.ranking import rank_quotes
from ..providers.calls.base import CallProvider
from .state import ProcurementAgentState


@dataclass
class AgentDependencies:
    sourcing_requests: dict[str, SourcingRequest]
    suppliers: dict[str, Supplier]
    quotes_by_request: dict[str, list[SupplierQuote]]
    provider: CallProvider


class ProcurementNodes:
    def __init__(self, dependencies: AgentDependencies) -> None:
        self.dependencies = dependencies

    def call_preview(self, state: ProcurementAgentState) -> dict:
        self._request(state)
        return {"workflow_status": "call_preview"}

    def awaiting_quote_approval(self, state: ProcurementAgentState) -> dict:
        return {"workflow_status": "awaiting_quote_approval"}

    def dispatch_supplier_calls(self, state: ProcurementAgentState) -> dict:
        if not state["quote_call_approved"]:
            return {
                "workflow_status": "awaiting_quote_approval",
                "errors": ["Explicit quote-call approval is required."],
            }
        sourcing_request = self._request(state)
        quotes = [
            self.dependencies.provider.create_quote_call(sourcing_request, supplier)
            for supplier in self.dependencies.suppliers.values()
        ]
        self.dependencies.quotes_by_request[sourcing_request.id] = quotes
        sourcing_request.status = "quotes_ready"
        return {
            "workflow_status": "supplier_calls_dispatched",
            "quotes": [quote.id for quote in quotes],
            "errors": [],
        }

    def normalize_quotes(self, state: ProcurementAgentState) -> dict:
        quotes = self.dependencies.quotes_by_request.get(
            state["sourcing_request_id"], []
        )
        return {
            "workflow_status": "quotes_normalized",
            "quotes": [quote.id for quote in quotes],
        }

    def rank_quotes(self, state: ProcurementAgentState) -> dict:
        sourcing_request = self._request(state)
        quotes = self.dependencies.quotes_by_request[sourcing_request.id]
        ranked = rank_quotes(sourcing_request, quotes, self.dependencies.suppliers)
        ranking = [item.quote.id for item in ranked]
        return {
            "workflow_status": "ranked",
            "ranking": ranking,
            "recommended_quote_id": ranking[0],
        }

    def awaiting_human_selection(self, state: ProcurementAgentState) -> dict:
        return {"workflow_status": "awaiting_human_selection"}

    def reservation_preview(self, state: ProcurementAgentState) -> dict:
        if not state["selected_quote_id"]:
            return {
                "workflow_status": "awaiting_human_selection",
                "errors": ["Explicit supplier selection is required."],
            }
        return {
            "workflow_status": "reservation_preview",
            "reservation_result": {
                "outcome": "pending_approval",
                "supplier_reference": None,
            },
            "errors": [],
        }

    def awaiting_reservation_approval(self, state: ProcurementAgentState) -> dict:
        return {"workflow_status": "awaiting_reservation_approval"}

    def reservation_call(self, state: ProcurementAgentState) -> dict:
        if not state["reservation_approved"]:
            return {
                "workflow_status": "awaiting_reservation_approval",
                "errors": ["Explicit reservation approval is required."],
            }
        sourcing_request = self._request(state)
        quote = self._selected_quote(state)
        supplier = self.dependencies.suppliers[quote.supplier_id]
        result = self.dependencies.provider.create_reservation_call(
            sourcing_request, quote, supplier
        )
        return {
            "workflow_status": "reservation_call",
            "reservation_result": result,
            "errors": [],
        }

    def completed(self, state: ProcurementAgentState) -> dict:
        return {"workflow_status": "completed"}

    def _request(self, state: ProcurementAgentState) -> SourcingRequest:
        return self.dependencies.sourcing_requests[state["sourcing_request_id"]]

    def _selected_quote(self, state: ProcurementAgentState) -> SupplierQuote:
        selected_quote_id = state["selected_quote_id"]
        quotes = self.dependencies.quotes_by_request[state["sourcing_request_id"]]
        return next(quote for quote in quotes if quote.id == selected_quote_id)
