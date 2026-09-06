from typing import NoReturn

from calle.calls import CalleCalls
from fastapi.testclient import TestClient

from backend.app.api import routes
from backend.tests.test_phase_a import approve_quotes, create_request


def test_workflow_pauses_before_quote_approval(
    monkeypatch, client: TestClient
) -> None:
    operations = 0
    original = routes.provider.create_quote_call

    def tracked_operation(*args, **kwargs):
        nonlocal operations
        operations += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(routes.provider, "create_quote_call", tracked_operation)
    request_id = create_request(client)
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "awaiting_quote_approval"
    assert response.json()["quote_call_approved"] is False
    assert operations == 0
    assert client.get(f"/api/v1/sourcing-requests/{request_id}/quotes").json() == []


def test_quote_approval_ranks_without_selecting(client: TestClient) -> None:
    request_id = create_request(client)
    client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")
    quotes = approve_quotes(client, request_id)
    workflow = client.get(
        f"/api/v1/sourcing-requests/{request_id}/workflow"
    ).json()
    ranking = client.get(
        f"/api/v1/sourcing-requests/{request_id}/ranking"
    ).json()

    assert len(quotes) == 3
    assert workflow["workflow_status"] == "awaiting_human_selection"
    assert workflow["recommended_quote_id"] == ranking["ranking"][0]["quote_id"]
    assert workflow["selected_quote_id"] is None
    assert [item["supplier_name"] for item in ranking["ranking"]] == [
        "Supplier A",
        "Supplier B",
        "Supplier C",
    ]


def test_selection_previews_reservation_but_does_not_execute(
    monkeypatch, client: TestClient
) -> None:
    reservation_operations = 0
    original = routes.provider.create_reservation_call

    def tracked_operation(*args, **kwargs):
        nonlocal reservation_operations
        reservation_operations += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(
        routes.provider, "create_reservation_call", tracked_operation
    )
    request_id = create_request(client)
    approve_quotes(client, request_id)
    ranking = client.get(
        f"/api/v1/sourcing-requests/{request_id}/ranking"
    ).json()
    supplier_a_quote = ranking["ranking"][0]["quote_id"]

    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": supplier_a_quote},
    )
    preview = client.post(
        f"/api/v1/sourcing-requests/{request_id}/reservation-preview"
    )

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "awaiting_reservation_approval"
    assert response.json()["selected_quote_id"] == supplier_a_quote
    assert response.json()["reservation_result"]["outcome"] == "pending_approval"
    assert preview.status_code == 200
    assert reservation_operations == 0


def test_reservation_preview_requires_explicit_selection(client: TestClient) -> None:
    request_id = create_request(client)
    approve_quotes(client, request_id)

    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/reservation-preview"
    )

    assert response.status_code == 409
    workflow = client.get(
        f"/api/v1/sourcing-requests/{request_id}/workflow"
    ).json()
    assert workflow["workflow_status"] == "awaiting_human_selection"
    assert workflow["selected_quote_id"] is None


def test_second_approval_completes_fake_reservation(
    monkeypatch, client: TestClient
) -> None:
    def fail_if_called(*args, **kwargs) -> NoReturn:
        raise AssertionError("CALL-E create was called")

    monkeypatch.setattr(CalleCalls, "create", fail_if_called)
    request_id = create_request(client)
    approve_quotes(client, request_id)
    ranking = client.get(
        f"/api/v1/sourcing-requests/{request_id}/ranking"
    ).json()
    supplier_a_quote = ranking["ranking"][0]["quote_id"]
    client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": supplier_a_quote},
    )

    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/approve-reservation"
    )

    assert response.status_code == 200
    assert response.json()["workflow_status"] == "completed"
    assert response.json()["reservation_approved"] is True
    assert response.json()["reservation_result"]["outcome"] == "confirmed"


def test_activity_exposes_factual_events_without_sensitive_payloads(
    client: TestClient,
) -> None:
    request_id = create_request(client)
    client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")
    approve_quotes(client, request_id)

    response = client.get(f"/api/v1/sourcing-requests/{request_id}/activity")

    assert response.status_code == 200
    events = response.json()
    assert events[0]["event_type"] == "request_created"
    assert "knowledge_retrieved" in [event["event_type"] for event in events]
    assert "quotes_normalized" in [event["event_type"] for event in events]
    assert all(set(event) == {"id", "event_type", "created_at"} for event in events)
