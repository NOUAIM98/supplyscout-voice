from langgraph.graph import END, START, StateGraph

from .nodes import AgentDependencies, ProcurementNodes
from .state import ProcurementAgentState


class ProcurementAgent:
    def __init__(self, dependencies: AgentDependencies) -> None:
        nodes = ProcurementNodes(dependencies)
        builder = StateGraph(ProcurementAgentState)
        builder.add_node("call_preview", nodes.call_preview)
        builder.add_node("awaiting_quote_approval", nodes.awaiting_quote_approval)
        builder.add_node("dispatch_supplier_calls", nodes.dispatch_supplier_calls)
        builder.add_node("normalize_quotes", nodes.normalize_quotes)
        builder.add_node("rank_quotes", nodes.rank_quotes)
        builder.add_node("awaiting_human_selection", nodes.awaiting_human_selection)
        builder.add_node("reservation_preview", nodes.reservation_preview)
        builder.add_node(
            "awaiting_reservation_approval", nodes.awaiting_reservation_approval
        )
        builder.add_node("reservation_call", nodes.reservation_call)
        builder.add_node("completed", nodes.completed)

        builder.add_conditional_edges(
            START,
            self._next_step,
            {
                "call_preview": "call_preview",
                "dispatch_supplier_calls": "dispatch_supplier_calls",
                "reservation_preview": "reservation_preview",
                "reservation_call": "reservation_call",
                "stop": END,
            },
        )
        builder.add_edge("call_preview", "awaiting_quote_approval")
        builder.add_edge("awaiting_quote_approval", END)
        builder.add_edge("dispatch_supplier_calls", "normalize_quotes")
        builder.add_edge("normalize_quotes", "rank_quotes")
        builder.add_edge("rank_quotes", "awaiting_human_selection")
        builder.add_edge("awaiting_human_selection", END)
        builder.add_edge("reservation_preview", "awaiting_reservation_approval")
        builder.add_edge("awaiting_reservation_approval", END)
        builder.add_edge("reservation_call", "completed")
        builder.add_edge("completed", END)
        self.graph = builder.compile()

    def initial_state(self, sourcing_request_id: str) -> ProcurementAgentState:
        return {
            "sourcing_request_id": sourcing_request_id,
            "workflow_status": "request_created",
            "quote_call_approved": False,
            "quotes": [],
            "ranking": [],
            "recommended_quote_id": None,
            "selected_quote_id": None,
            "reservation_approved": False,
            "reservation_result": None,
            "errors": [],
        }

    def run(self, state: ProcurementAgentState) -> ProcurementAgentState:
        return self.graph.invoke(state)

    def run_with_transitions(
        self, state: ProcurementAgentState
    ) -> tuple[ProcurementAgentState, list[str]]:
        current = dict(state)
        transitions = []
        for event in self.graph.stream(state, stream_mode="updates"):
            for update in event.values():
                if update:
                    current.update(update)
                    transitions.append(update["workflow_status"])
        return current, transitions

    @staticmethod
    def _next_step(state: ProcurementAgentState) -> str:
        status = state["workflow_status"]
        if status == "request_created":
            return "call_preview"
        if status == "awaiting_quote_approval" and state["quote_call_approved"]:
            return "dispatch_supplier_calls"
        if status == "awaiting_human_selection" and state["selected_quote_id"]:
            return "reservation_preview"
        if status == "awaiting_reservation_approval" and state["reservation_approved"]:
            return "reservation_call"
        return "stop"
