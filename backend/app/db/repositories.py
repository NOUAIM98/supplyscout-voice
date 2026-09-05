from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from .models import AuditEvent, CallAttempt, Reservation, SourcingRequest
from .models import SourcingRequestSupplier, Supplier, SupplierQuote


class SupplierRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, supplier: Supplier) -> Supplier:
        return self.session.merge(supplier)

    def all(self) -> list[Supplier]:
        return list(self.session.scalars(select(Supplier).order_by(Supplier.name)))

    def assigned_to(self, request_id: str) -> list[Supplier]:
        statement = (
            select(Supplier)
            .join(SourcingRequestSupplier)
            .where(SourcingRequestSupplier.sourcing_request_id == request_id)
            .order_by(Supplier.name)
        )
        return list(self.session.scalars(statement))


class SourcingRequestRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, request: SourcingRequest) -> SourcingRequest:
        self.session.add(request)
        return request

    def get(self, request_id: str) -> SourcingRequest | None:
        return self.session.get(SourcingRequest, request_id)

    def assign_supplier(self, request_id: str, supplier_id: str) -> None:
        self.session.add(SourcingRequestSupplier(
            id=str(uuid4()), sourcing_request_id=request_id, supplier_id=supplier_id
        ))


class QuoteRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, quote: SupplierQuote) -> SupplierQuote:
        return self.session.merge(quote)

    def list_for_request(self, request_id: str) -> list[SupplierQuote]:
        return list(self.session.scalars(
            select(SupplierQuote).where(SupplierQuote.sourcing_request_id == request_id)
        ))

    def get(self, quote_id: str) -> SupplierQuote | None:
        return self.session.get(SupplierQuote, quote_id)


class ReservationRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, reservation: Reservation) -> Reservation:
        self.session.add(reservation)
        return reservation

    def for_request(self, request_id: str) -> Reservation | None:
        return self.session.scalar(
            select(Reservation).where(Reservation.sourcing_request_id == request_id)
        )


class AuditRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record(self, request_id: str, event_type: str, payload: dict | None = None) -> AuditEvent:
        event = AuditEvent(
            id=str(uuid4()), sourcing_request_id=request_id,
            event_type=event_type, safe_payload=payload or {}
        )
        self.session.add(event)
        return event

    def list_for_request(self, request_id: str) -> list[AuditEvent]:
        return list(self.session.scalars(
            select(AuditEvent).where(AuditEvent.sourcing_request_id == request_id)
            .order_by(AuditEvent.created_at)
        ))


class CallAttemptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def add(self, attempt: CallAttempt) -> CallAttempt:
        self.session.add(attempt)
        return attempt
