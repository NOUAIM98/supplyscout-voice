from datetime import date, datetime, timezone
from decimal import Decimal
from typing import NoReturn

import httpx
from calle.calls import CalleCalls
from fastapi.testclient import TestClient

from backend.app.config import Settings
from backend.app.db.models import SourcingRequest
from backend.app.providers.calls.fake import FakeCallProvider


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


def create_request(client: TestClient) -> str:
    response = client.post("/api/v1/sourcing-requests", json=DEMO_REQUEST)
    assert response.status_code == 201
    return response.json()["id"]


def approve_quotes(client: TestClient, request_id: str) -> list[dict]:
    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls"
    )
    assert response.status_code == 200
    return response.json()


def test_health_returns_200(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_settings_default_to_fake_without_calle_api_key(monkeypatch) -> None:
    monkeypatch.delenv("CALL_PROVIDER_MODE", raising=False)
    monkeypatch.delenv("CALLE_API_KEY", raising=False)
    isolated_settings = Settings(_env_file=None)
    assert isolated_settings.call_provider_mode == "fake"


def test_fake_provider_performs_no_network_request(monkeypatch) -> None:
    def fail_if_requested(*args, **kwargs) -> NoReturn:
        raise AssertionError("FakeCallProvider attempted a network request")

    monkeypatch.setattr(httpx.Client, "request", fail_if_requested)
    now = datetime.now(timezone.utc)
    sourcing_request = SourcingRequest(
        id="test-request",
        vehicle_make="Renault",
        vehicle_model="Clio",
        vehicle_year=2019,
        part_name="Alternator",
        requested_reference="TEST-ALT-CLIO-2019-001",
        quantity=1,
        max_budget=Decimal("180.00"),
        currency="EUR",
        needed_by=date.today(),
        status="draft",
        created_at=now,
        updated_at=now,
    )
    provider = FakeCallProvider()
    assert len(provider.collect_quotes(sourcing_request, provider.suppliers())) == 3


def test_create_sourcing_request(client: TestClient) -> None:
    request_id = create_request(client)
    assert request_id
    response = client.get(f"/api/v1/sourcing-requests/{request_id}")
    assert response.status_code == 200
    assert response.json()["requested_reference"] == DEMO_REQUEST["requested_reference"]


def test_approving_quote_calls_returns_three_quotes(client: TestClient) -> None:
    request_id = create_request(client)
    quotes = approve_quotes(client, request_id)
    assert len(quotes) == 3
    stored_quotes = client.get(f"/api/v1/sourcing-requests/{request_id}/quotes")
    assert stored_quotes.status_code == 200
    assert len(stored_quotes.json()) == 3


def test_demo_ranking_is_explainable_and_deterministic(client: TestClient) -> None:
    request_id = create_request(client)
    approve_quotes(client, request_id)

    response = client.get(f"/api/v1/sourcing-requests/{request_id}/ranking")
    assert response.status_code == 200
    result = response.json()
    assert [item["supplier_name"] for item in result["ranking"]] == [
        "Supplier A",
        "Supplier B",
        "Supplier C",
    ]
    assert result["recommended_supplier_name"] == "Supplier A"
    assert "meets the required deadline" in result["explanation"]
    assert "Misses the required deadline." in result["ranking"][1]["reasons"]
    assert "Exact requested reference is not confirmed." in result["ranking"][2]["reasons"]


def test_approval_does_not_call_calle_sdk(monkeypatch, client: TestClient) -> None:
    def fail_if_called(*args, **kwargs) -> NoReturn:
        raise AssertionError("CALL-E create was called")

    monkeypatch.setattr(CalleCalls, "create", fail_if_called)
    quotes = approve_quotes(client, create_request(client))
    assert len(quotes) == 3
