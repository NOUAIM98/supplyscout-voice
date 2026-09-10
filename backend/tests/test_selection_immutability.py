from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app.db.models import CallAttempt, Reservation, SourcingRequest, SupplierQuote
from backend.app.db.repositories import AuditRepository
from backend.tests.test_phase_a import approve_quotes, create_request


def _selection_stage(
    client: TestClient, session_factory,
) -> tuple[str, list[dict]]:
    request_id = create_request(client)
    quotes = approve_quotes(client, request_id)
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        assert request is not None
        request.selected_quote_id = quotes[0]["id"]
        session.commit()
    return request_id, quotes


def _assert_selection_rejected(
    client: TestClient, session_factory, request_id: str, replacement_id: str,
) -> None:
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        assert request is not None
        original_id = request.selected_quote_id

    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": replacement_id},
    )

    assert response.status_code == 409
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        assert request is not None
        assert request.selected_quote_id == original_id


def test_supplier_can_change_during_human_selection(
    client: TestClient, session_factory,
) -> None:
    request_id, quotes = _selection_stage(client, session_factory)

    response = client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": quotes[1]["id"]},
    )

    assert response.status_code == 200
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        assert request is not None
        assert request.selected_quote_id == quotes[1]["id"]


def test_selection_rejected_after_reservation_preview(
    client: TestClient, session_factory,
) -> None:
    request_id = create_request(client)
    quotes = approve_quotes(client, request_id)
    client.post(
        f"/api/v1/sourcing-requests/{request_id}/select-quote",
        json={"quote_id": quotes[0]["id"]},
    )

    _assert_selection_rejected(
        client, session_factory, request_id, quotes[1]["id"]
    )


def test_selection_rejected_after_reservation_approval(
    client: TestClient, session_factory,
) -> None:
    request_id, quotes = _selection_stage(client, session_factory)
    with session_factory() as session:
        AuditRepository(session).record(request_id, "reservation_approved")
        session.commit()

    _assert_selection_rejected(
        client, session_factory, request_id, quotes[1]["id"]
    )


def test_selection_rejected_after_reservation_call_started(
    client: TestClient, session_factory,
) -> None:
    request_id, quotes = _selection_stage(client, session_factory)
    with session_factory() as session:
        selected = session.get(SupplierQuote, quotes[0]["id"])
        assert selected is not None
        session.add(CallAttempt(
            id=str(uuid4()),
            sourcing_request_id=request_id,
            supplier_id=selected.supplier_id,
            call_type="reservation",
            logical_idempotency_key=f"test:reservation:{request_id}",
            attempt_number=1,
            status="started",
        ))
        session.commit()

    _assert_selection_rejected(
        client, session_factory, request_id, quotes[1]["id"]
    )


def test_selection_rejected_after_reservation_confirmed(
    client: TestClient, session_factory,
) -> None:
    request_id, quotes = _selection_stage(client, session_factory)
    with session_factory() as session:
        selected = session.get(SupplierQuote, quotes[0]["id"])
        assert selected is not None
        session.add(Reservation(
            id=str(uuid4()),
            sourcing_request_id=request_id,
            supplier_quote_id=selected.id,
            supplier_id=selected.supplier_id,
            status="confirmed",
            reservation_reference="TEST-RESERVATION",
        ))
        session.commit()

    _assert_selection_rejected(
        client, session_factory, request_id, quotes[1]["id"]
    )


def test_completed_request_selection_change_is_rejected(
    client: TestClient, session_factory,
) -> None:
    request_id, quotes = _selection_stage(client, session_factory)
    with session_factory() as session:
        request = session.get(SourcingRequest, request_id)
        assert request is not None
        request.status = "completed"
        session.commit()

    _assert_selection_rejected(
        client, session_factory, request_id, quotes[1]["id"]
    )
