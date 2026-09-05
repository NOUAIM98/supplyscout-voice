import sys
from datetime import date
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from fastapi.testclient import TestClient

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


def main() -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    client = TestClient(app)
    request = client.post("/api/v1/sourcing-requests", json=DEMO_REQUEST).json()
    request_id = request["id"]
    print("request_created")

    preview = client.post(
        f"/api/v1/sourcing-requests/{request_id}/quote-preview"
    ).json()
    print(preview["workflow_status"])
    print("STOP — human quote approval required")

    print("human approves quote calls")
    client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    ranking = client.get(
        f"/api/v1/sourcing-requests/{request_id}/ranking"
    ).json()
    print("awaiting_human_selection")
    print("STOP — human supplier selection required")

    print("human selects recommended Supplier A quote")
    client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": ranking["ranking"][0]["quote_id"]},
    )
    print("awaiting_reservation_approval")
    print("STOP — human reservation approval required")

    print("human approves reservation")
    completed = client.post(
        f"/api/v1/sourcing-requests/{request_id}/approve-reservation"
    ).json()
    print(f"workflow status: {completed['workflow_status']}")
    print(f"fake reservation outcome: {completed['reservation_result']['outcome']}")


if __name__ == "__main__":
    main()
