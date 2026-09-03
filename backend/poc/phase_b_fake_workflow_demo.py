import sys
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app.main import app


DEMO_REQUEST = {
    "vehicle_make": "Renault",
    "vehicle_model": "Clio",
    "vehicle_year": 2019,
    "part_name": "Alternator",
    "requested_reference": "TEST-ALT-CLIO-2019-001",
    "quantity": 1,
    "max_budget": "180.00",
    "currency": "EUR",
    "needed_by": date.today().isoformat(),
}


def advance(state: dict, **updates) -> dict:
    state, transitions = routes.agent.run_with_transitions({**state, **updates})
    for transition in transitions:
        print(f"→ {transition}")
    routes.workflow_states[state["sourcing_request_id"]] = state
    return state


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = TestClient(app)
    request = client.post("/api/v1/sourcing-requests", json=DEMO_REQUEST).json()
    state = routes.workflow_states[request["id"]]
    print("request_created")

    state = advance(state)
    print("STOP — human quote approval required")

    print("human approves quote calls")
    state = advance(state, quote_call_approved=True)
    print("STOP — human supplier selection required")

    print("human selects recommended Supplier A quote")
    state = advance(state, selected_quote_id=state["recommended_quote_id"])
    print("STOP — human reservation approval required")

    print("human approves reservation")
    state = advance(state, reservation_approved=True)
    print(f"fake reservation outcome: {state['reservation_result']['outcome']}")


if __name__ == "__main__":
    main()
