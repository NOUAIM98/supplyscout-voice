from typing import Any, NoReturn
from uuid import uuid4

import httpx
import pytest
from calle.calls import CalleCalls
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from backend.app.db.models import AuditEvent, CallAttempt, Reservation
from backend.app.db.models import SourcingRequest, SourcingRequestSupplier, Supplier
from backend.app.db.models import SupplierQuote
from backend.tests.test_phase_a import approve_quotes, create_request


def test_request_supplier_and_assignment_persist(client: TestClient, session_factory) -> None:
    request_id = create_request(client)

    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        suppliers = list(session.scalars(select(Supplier)))
        assignments = list(session.scalars(select(SourcingRequestSupplier)))

    assert request is not None
    assert request.max_budget.as_tuple().exponent == -2
    assert len(suppliers) == 3
    assert len(assignments) == 3


def test_quotes_survive_new_session_and_preserve_missing_values(
    client: TestClient, session_factory,
) -> None:
    request_id = create_request(client)
    approve_quotes(client, request_id)

    with session_factory() as session:
        quotes = list(session.scalars(
            select(SupplierQuote).where(SupplierQuote.sourcing_request_id == request_id)
        ))
        uncertain = next(q for q in quotes if q.exact_reference_confirmed == "unknown")

    assert len(quotes) == 3
    assert uncertain.offered_reference is None
    assert uncertain.manufacturer_or_brand is None
    assert uncertain.quantity_available is None


def test_ranking_reads_persisted_quotes(client: TestClient) -> None:
    request_id = create_request(client)
    approve_quotes(client, request_id)

    response = client.get(f"/api/v1/sourcing-requests/{request_id}/ranking")

    assert [item["supplier_name"] for item in response.json()["ranking"]] == [
        "Supplier A", "Supplier B", "Supplier C"
    ]


def test_selection_and_reservation_status_persist(client: TestClient, session_factory) -> None:
    request_id = create_request(client)
    quotes = approve_quotes(client, request_id)
    selected_quote_id = quotes[0]["id"]

    selection = client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": selected_quote_id},
    )

    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        reservation = session.scalar(
            select(Reservation).where(Reservation.sourcing_request_id == request_id)
        )
    assert selection.json()["workflow_status"] == "awaiting_reservation_approval"
    assert request is not None and request.selected_quote_id == selected_quote_id
    assert reservation is not None and reservation.status == "pending_approval"


def test_reservation_still_requires_second_approval(client: TestClient, session_factory) -> None:
    request_id = create_request(client)
    selected = approve_quotes(client, request_id)[0]["id"]
    client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": selected},
    )

    with session_factory() as session:
        reservation = session.scalar(select(Reservation))
        assert reservation is not None and reservation.status == "pending_approval"


def test_audit_events_and_call_attempts_are_persisted(client: TestClient, session_factory) -> None:
    request_id = create_request(client)
    client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")
    approve_quotes(client, request_id)

    with session_factory() as session:
        events = list(session.scalars(
            select(AuditEvent).where(AuditEvent.sourcing_request_id == request_id)
        ))
        attempts = list(session.scalars(select(CallAttempt)))
    event_types = {event.event_type for event in events}
    assert {"request_created", "preview_generated", "quote_calls_approved"} <= event_types
    assert "structured_quote_stored" in event_types
    assert len(attempts) == 3


def test_duplicate_request_supplier_assignment_is_prevented(
    client: TestClient, session_factory,
) -> None:
    request_id = create_request(client)
    with session_factory() as session:
        existing = session.scalar(select(SourcingRequestSupplier))
        assert existing is not None
        session.add(SourcingRequestSupplier(
            id=str(uuid4()), sourcing_request_id=request_id,
            supplier_id=existing.supplier_id,
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_duplicate_logical_call_attempt_is_prevented(client: TestClient, session_factory) -> None:
    request_id = create_request(client)
    approve_quotes(client, request_id)
    with session_factory() as session:
        existing = session.scalar(select(CallAttempt))
        assert existing is not None
        session.add(CallAttempt(
            id=str(uuid4()), sourcing_request_id=request_id,
            supplier_id=existing.supplier_id, call_type="quote",
            logical_idempotency_key=existing.logical_idempotency_key,
            attempt_number=existing.attempt_number, status="started",
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_full_fake_workflow_persists_without_calle_network(
    monkeypatch, client: TestClient, session_factory
) -> None:
    def fail_create(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("CALL-E create was invoked")

    def fail_network(*args: Any, **kwargs: Any) -> NoReturn:
        raise AssertionError("Network was invoked")

    monkeypatch.setattr(CalleCalls, "create", fail_create)
    monkeypatch.setattr(httpx.Client, "request", fail_network)
    request_id = create_request(client)
    client.post(f"/api/v1/sourcing-requests/{request_id}/quote-preview")
    quotes = approve_quotes(client, request_id)
    ranking = client.get(f"/api/v1/sourcing-requests/{request_id}/ranking").json()
    selected = ranking["ranking"][0]["quote_id"]
    client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": selected},
    )
    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/approve-reservation"
    )

    assert len(quotes) == 3
    assert response.json()["workflow_status"] == "completed"
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        reservation = session.scalar(select(Reservation))
        attempts = list(session.scalars(select(CallAttempt)))
    assert request is not None and request.status == "completed"
    assert reservation is not None and reservation.status == "confirmed"
    assert len(attempts) == 4
