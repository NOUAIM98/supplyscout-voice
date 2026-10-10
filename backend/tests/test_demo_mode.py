from typing import Any

from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.app.providers.calls.calle import CalleCallProvider
from backend.tests.test_phase_a import DEMO_REQUEST


class ForbiddenCalls:
    def create(self, **kwargs: Any) -> dict[str, Any]:
        raise AssertionError("Demo mode must never create a CALL-E call")


class ForbiddenCalleClient:
    calls = ForbiddenCalls()


def test_demo_request_completes_while_global_live_calls_are_disabled(
    client: TestClient, monkeypatch
) -> None:
    monkeypatch.setattr(
        routes,
        "provider",
        CalleCallProvider(api_key="fictional-test-key", client=ForbiddenCalleClient()),
    )
    monkeypatch.setattr(routes.settings, "call_provider_mode", "calle")
    monkeypatch.setattr(routes.settings, "calle_live_enabled", False)
    monkeypatch.setattr(routes.settings, "portfolio_demo_only", True)

    created = client.post("/api/v1/demo/sourcing-requests", json=DEMO_REQUEST)
    assert created.status_code == 201
    request_id = created.json()["id"]

    preview = client.post(
        f"/api/v1/sourcing-requests/{request_id}/quote-preview"
    ).json()
    assert preview["call_preview"] == {
        "demo_mode": True,
        "requested_reference": DEMO_REQUEST["requested_reference"],
        "quantity": 1,
        "supplier_count": 3,
        "supplier_names": ["Supplier A", "Supplier B", "Supplier C"],
    }
    context = client.post(
        f"/api/v1/sourcing-requests/{request_id}/context-preview"
    ).json()
    assert context["mode"] == "demo"
    assert context["call_started"] is False
    assert context["chunks"]
    assert {chunk["scope"] for chunk in context["chunks"]} == {
        "reference_specific", "general"
    }

    quotes = client.post(
        f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls"
    )
    assert quotes.status_code == 200
    assert len(quotes.json()) == 3
    ranking = client.get(f"/api/v1/sourcing-requests/{request_id}/ranking").json()
    assert [entry["supplier_name"] for entry in ranking["ranking"]] == [
        "Supplier A", "Supplier B"
    ]

    selected = ranking["ranking"][0]["quote_id"]
    assert client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": selected},
    ).status_code == 200
    completed = client.post(
        f"/api/v1/sourcing-requests/{request_id}/approve-reservation"
    )
    assert completed.status_code == 200
    assert completed.json()["workflow_status"] == "completed"
    assert completed.json()["reservation_result"]["outcome"] == "confirmed"


def test_portfolio_mode_rejects_non_demo_api(client: TestClient, monkeypatch) -> None:
    monkeypatch.setattr(routes.settings, "portfolio_demo_only", True)
    response = client.post("/api/v1/sourcing-requests", json=DEMO_REQUEST)
    assert response.status_code == 403
    assert response.json()["detail"] == "Only the isolated fictional demo API is enabled"


def test_demo_creation_is_rate_limited(client: TestClient, monkeypatch) -> None:
    routes._demo_create_attempts.clear()
    monkeypatch.setattr(routes.settings, "demo_create_rate_limit", 2)
    monkeypatch.setattr(routes.settings, "demo_create_rate_window_seconds", 3600)
    try:
        assert client.post("/api/v1/demo/sourcing-requests", json=DEMO_REQUEST).status_code == 201
        assert client.post("/api/v1/demo/sourcing-requests", json=DEMO_REQUEST).status_code == 201
        response = client.post("/api/v1/demo/sourcing-requests", json=DEMO_REQUEST)
        assert response.status_code == 429
        assert response.json()["detail"] == "Demo request limit reached. Please try again later."
    finally:
        routes._demo_create_attempts.clear()
