from __future__ import annotations

import logging
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from backend.app.api import routes
from backend.app.config import Settings
from backend.app.db.models import AuditEvent, CallAttempt, Reservation, SourcingRequest, Supplier
from backend.app.providers.calls.calle import CalleCallProvider
from backend.app.providers.calls.fake import FakeCallProvider
from backend.app.providers.calls.guard import LiveCallBlocked, assert_live_call_allowed, mask_phone
from backend.tests.test_phase_a import create_request


def quote_result(call_id: str, status: str = "completed") -> dict[str, Any]:
    return {
        "id": call_id,
        "status": status,
        "recipients": [{"structured_result": {
            "exact_reference_confirmed": "yes",
            "in_stock": "yes",
            "condition": "new",
            "tax_included": "unknown",
            "pickup_available_today": "yes",
            "offered_reference": "TEST-ALT-CLIO-2019-001",
            "unit_price": 145,
            "currency": "EUR",
        }}],
    }


class StubCalls:
    def __init__(self) -> None:
        self.created: list[dict[str, Any]] = []
        self.responses: dict[str, dict[str, Any]] = {}

    def create(self, **kwargs: Any) -> dict[str, Any]:
        self.created.append(kwargs)
        call_id = f"fictional-call-{len(self.created)}"
        self.responses[call_id] = {"id": call_id, "status": "queued", "recipients": [{}]}
        return self.responses[call_id]

    def get(self, call_id: str) -> dict[str, Any]:
        return self.responses[call_id]


class StubClient:
    def __init__(self) -> None:
        self.calls = StubCalls()


@pytest.fixture
def live_app(monkeypatch, client: TestClient):
    fake = FakeCallProvider()
    monkeypatch.setattr(routes, "provider", fake)
    request_id = create_request(client)
    client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")
    suppliers = list(fake.suppliers())
    stub = StubClient()
    recipients = {
        supplier.id: {"phones": [supplier.phone_e164], "region": "US", "locale": "en-US"}
        for supplier in suppliers
    }
    provider = CalleCallProvider(
        api_key="fictional-test-key", recipients=recipients, client=stub
    )
    monkeypatch.setattr(routes, "provider", provider)
    monkeypatch.setattr(routes.settings, "call_provider_mode", "calle")
    monkeypatch.setattr(routes.settings, "calle_live_enabled", True)
    monkeypatch.setattr(routes.settings, "calle_allowed_recipients", ",".join(s.phone_e164 for s in suppliers))
    monkeypatch.setattr(routes.settings, "calle_recipient_region", "US")
    monkeypatch.setattr(routes.settings, "calle_recipient_locale", "en-US")
    return request_id, suppliers, stub


def test_fake_and_live_guards_default_closed() -> None:
    settings = Settings(_env_file=None)
    assert settings.call_provider_mode == "fake"
    assert settings.calle_live_enabled is False
    assert settings.allowed_calle_recipients == frozenset()


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"call_provider_mode": "fake"}, "not selected"),
        ({"calle_live_enabled": False}, "disabled"),
        ({"calle_allowed_recipients": ""}, "allowlisted"),
        ({"calle_recipient_region": None}, "region and locale"),
        ({"calle_recipient_locale": None}, "region and locale"),
    ],
)
def test_live_guard_fails_closed(live_app, db_session, change, message) -> None:
    request_id, suppliers, _ = live_app
    request = db_session.get(SourcingRequest, request_id)
    db_session.add(AuditEvent(id="approval", sourcing_request_id=request_id, event_type="quote_calls_approved", safe_payload={}))
    db_session.flush()
    isolated = routes.settings.model_copy(update=change)
    with pytest.raises(LiveCallBlocked, match=message):
        assert_live_call_allowed(db_session, isolated, request, suppliers[0], "quote")


def test_guard_rejects_malformed_phone_and_unassigned_supplier(live_app, db_session) -> None:
    request_id, suppliers, _ = live_app
    request = db_session.get(SourcingRequest, request_id)
    db_session.add(AuditEvent(id="approval", sourcing_request_id=request_id, event_type="quote_calls_approved", safe_payload={}))
    malformed = Supplier(id="bad", name="Bad", phone_e164="invalid", authorized_for_calls=True)
    with pytest.raises(LiveCallBlocked, match="E.164"):
        assert_live_call_allowed(db_session, routes.settings, request, malformed, "quote")
    unassigned = Supplier(id="other", name="Other", phone_e164=suppliers[0].phone_e164, authorized_for_calls=True)
    with pytest.raises(LiveCallBlocked, match="not assigned"):
        assert_live_call_allowed(db_session, routes.settings, request, unassigned, "quote")


def test_guard_requires_persisted_quote_approval(live_app, db_session) -> None:
    request_id, suppliers, _ = live_app
    request = db_session.get(SourcingRequest, request_id)
    with pytest.raises(LiveCallBlocked, match="Persisted quote-call approval"):
        assert_live_call_allowed(db_session, routes.settings, request, suppliers[0], "quote")


def test_live_disabled_application_dry_run_creates_no_calls(live_app, monkeypatch, client) -> None:
    request_id, _, stub = live_app
    monkeypatch.setattr(routes.settings, "calle_live_enabled", False)
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    assert response.status_code == 403
    assert response.json()["detail"] == "Live calls are disabled"
    assert stub.calls.created == []


def test_live_dispatch_is_nonblocking_idempotent_and_persists_ids(live_app, client, session_factory) -> None:
    request_id, suppliers, stub = live_app
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    assert response.status_code == 200
    assert response.json() == []
    assert len(stub.calls.created) == 3
    assert [item["idempotency_key"] for item in stub.calls.created] == [
        f"supplyscout:quote:{request_id}:{supplier.id}" for supplier in suppliers
    ]
    with session_factory() as session:
        attempts = list(session.scalars(select(CallAttempt).order_by(CallAttempt.supplier_id)))
        assert len(attempts) == 3
        assert all(item.provider_call_id and item.status == "queued" for item in attempts)
    repeated = client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    assert repeated.status_code == 409
    assert len(stub.calls.created) == 3


def test_sync_waits_then_normalizes_once_preserving_unknowns(live_app, client, session_factory) -> None:
    request_id, _, stub = live_app
    client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    active = client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls")
    assert active.status_code == 200
    assert active.json()["workflow"]["workflow_status"] == "supplier_calls_dispatched"
    assert client.get(f"/api/v1/sourcing-requests/{request_id}/quotes").json() == []
    for call_id in list(stub.calls.responses):
        stub.calls.responses[call_id] = quote_result(call_id)
    completed = client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls")
    quotes = client.get(f"/api/v1/sourcing-requests/{request_id}/quotes").json()
    assert completed.json()["workflow"]["workflow_status"] == "awaiting_human_selection"
    assert len(quotes) == 3
    assert all(item["manufacturer_or_brand"] is None for item in quotes)
    client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls")
    assert len(client.get(f"/api/v1/sourcing-requests/{request_id}/quotes").json()) == 3
    assert len(stub.calls.created) == 3
    with session_factory() as session:
        assert len(list(session.scalars(select(CallAttempt)))) == 3


def test_unknown_provider_status_stays_pending(live_app, client) -> None:
    request_id, _, stub = live_app
    client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    for call_id in list(stub.calls.responses):
        stub.calls.responses[call_id] = {"id": call_id, "status": "mystery", "recipients": [{}]}
    result = client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls").json()
    assert all(item["status"] == "in_progress" for item in result["attempts"])


def test_provider_failure_is_persisted_safely(live_app, client) -> None:
    request_id, _, stub = live_app
    client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    for call_id in list(stub.calls.responses):
        stub.calls.responses[call_id] = {"id": call_id, "status": "failed", "recipients": [{}]}
    result = client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls").json()
    assert all(item["status"] == "failed" for item in result["attempts"])
    assert len(stub.calls.created) == 3


def test_ambiguous_dispatch_failure_is_persisted_without_retry(
    live_app, client, session_factory, caplog, monkeypatch
) -> None:
    request_id, _, stub = live_app
    monkeypatch.setattr(logging.getLogger("backend.app.agent.nodes"), "disabled", False)
    caplog.set_level(logging.ERROR, logger="backend.app.agent.nodes")

    def fail_create(**kwargs: Any) -> dict[str, Any]:
        raise TimeoutError("fictional provider timeout")

    stub.calls.create = fail_create
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    assert response.status_code == 200
    assert caplog.text.count("CALL-E quote dispatch failed") == 3
    assert f"request_id={request_id}" in caplog.text
    assert "exception_type=TimeoutError" in caplog.text
    assert "exception_message=fictional provider timeout" in caplog.text
    assert "fictional-test-key" not in caplog.text
    assert all(supplier.phone_e164 not in caplog.text for supplier in live_app[1])
    assert "Authorization" not in caplog.text
    with session_factory() as session:
        attempts = list(session.scalars(select(CallAttempt)))
        assert len(attempts) == 3
        assert all(item.status == "failed" and item.provider_call_id is None for item in attempts)
    assert client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls").status_code == 409


def test_reservation_dispatch_failure_is_logged_safely_without_retry(
    live_app, client, session_factory, caplog, monkeypatch
) -> None:
    request_id, suppliers, stub = live_app
    monkeypatch.setattr(logging.getLogger("backend.app.agent.nodes"), "disabled", False)
    caplog.set_level(logging.ERROR, logger="backend.app.agent.nodes")
    quotes = complete_quotes(request_id, stub, client)
    client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": quotes[0]["id"]},
    )

    def fail_create(**kwargs: Any) -> dict[str, Any]:
        raise ConnectionError("fictional reservation connection error")

    before = len(stub.calls.created)
    stub.calls.create = fail_create
    response = client.post(f"/api/v1/sourcing-requests/{request_id}/approve-reservation")

    assert response.status_code == 200
    assert response.json()["reservation_result"]["outcome"] == "failed"
    assert "CALL-E reservation dispatch failed" in caplog.text
    assert f"request_id={request_id}" in caplog.text
    assert "exception_type=ConnectionError" in caplog.text
    assert "exception_message=fictional reservation connection error" in caplog.text
    assert "fictional-test-key" not in caplog.text
    assert all(supplier.phone_e164 not in caplog.text for supplier in suppliers)
    assert "Authorization" not in caplog.text
    assert len(stub.calls.created) == before
    with session_factory() as session:
        attempt = session.scalar(
            select(CallAttempt).where(CallAttempt.call_type == "reservation")
        )
        reservation = session.scalar(select(Reservation))
        assert attempt is not None
        assert attempt.status == "failed" and attempt.provider_call_id is None
        assert reservation is not None and reservation.status == "failed"
    assert client.post(f"/api/v1/sourcing-requests/{request_id}/approve-reservation").status_code == 409


def complete_quotes(request_id: str, stub: StubClient, client: TestClient) -> list[dict]:
    client.post(f"/api/v1/sourcing-requests/{request_id}/approve-quote-calls")
    for call_id in list(stub.calls.responses):
        stub.calls.responses[call_id] = quote_result(call_id)
    client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls")
    return client.get(f"/api/v1/sourcing-requests/{request_id}/quotes").json()


def test_reservation_needs_selection_and_separate_approval(live_app, client, db_session) -> None:
    request_id, suppliers, stub = live_app
    complete_quotes(request_id, stub, client)
    request = db_session.get(SourcingRequest, request_id)
    with pytest.raises(LiveCallBlocked, match="Separate persisted reservation approval"):
        assert_live_call_allowed(db_session, routes.settings, request, suppliers[0], "reservation")


@pytest.mark.parametrize("outcome", ["unclear", "no_answer", "confirmed"])
def test_live_reservation_dispatch_and_sync_outcomes(live_app, client, session_factory, outcome) -> None:
    request_id, _, stub = live_app
    quotes = complete_quotes(request_id, stub, client)
    selected = quotes[0]
    client.post(f"/api/v1/sourcing-requests/{request_id}/select-quote", json={"quote_id": selected["id"]})
    before = len(stub.calls.created)
    dispatched = client.post(f"/api/v1/sourcing-requests/{request_id}/approve-reservation")
    assert dispatched.status_code == 200
    assert dispatched.json()["reservation_result"]["outcome"] == "calling"
    assert len(stub.calls.created) == before + 1
    reservation_request = stub.calls.created[-1]
    supplier_id = selected["supplier_id"]
    assert reservation_request["idempotency_key"] == f"supplyscout:reservation:{request_id}:{supplier_id}"
    call_id = f"fictional-call-{len(stub.calls.created)}"
    stub.calls.responses[call_id] = {"id": call_id, "status": "completed", "recipients": [{"structured_result": {"outcome": outcome}}]}
    synced = client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls").json()
    assert synced["workflow"]["reservation_result"]["outcome"] == outcome
    assert synced["workflow"]["workflow_status"] == "completed"
    client.post(f"/api/v1/sourcing-requests/{request_id}/sync-calls")
    assert len(stub.calls.created) == before + 1
    with session_factory() as session:
        reservation = session.scalar(select(Reservation))
        assert reservation is not None and reservation.status == outcome


def test_runtime_endpoint_is_safe(live_app, client) -> None:
    response = client.get("/api/v1/runtime")
    assert response.json() == {"call_provider_mode": "calle", "live_calls_enabled": True}
    serialized = response.text.lower()
    assert "key" not in serialized and "recipient" not in serialized and "database" not in serialized


def test_phone_mask_never_returns_full_recipient() -> None:
    fictional = "+12025550101"
    masked = mask_phone(fictional)
    assert masked == "+12******101"
    assert fictional not in masked
