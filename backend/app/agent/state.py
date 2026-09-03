from typing import Literal, TypedDict


WorkflowStatus = Literal[
    "request_created",
    "call_preview",
    "awaiting_quote_approval",
    "supplier_calls_dispatched",
    "quotes_normalized",
    "ranked",
    "awaiting_human_selection",
    "reservation_preview",
    "awaiting_reservation_approval",
    "reservation_call",
    "completed",
]

ReservationOutcome = Literal[
    "pending_approval",
    "calling",
    "confirmed",
    "refused",
    "unavailable",
    "unclear",
    "no_answer",
    "failed",
]


class ReservationResult(TypedDict):
    outcome: ReservationOutcome
    supplier_reference: str | None


class ProcurementAgentState(TypedDict):
    sourcing_request_id: str
    workflow_status: WorkflowStatus
    quote_call_approved: bool
    quotes: list[str]
    ranking: list[str]
    recommended_quote_id: str | None
    selected_quote_id: str | None
    reservation_approved: bool
    reservation_result: ReservationResult | None
    errors: list[str]
