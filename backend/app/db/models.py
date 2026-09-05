from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import JSON, Boolean, CheckConstraint, Date, DateTime, ForeignKey
from sqlalchemy import Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class Supplier(TimestampMixin, Base):
    __tablename__ = "suppliers"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone_e164: Mapped[str] = mapped_column(String(16), unique=True)
    authorized_for_calls: Mapped[bool] = mapped_column(Boolean, default=False)


class SourcingRequest(TimestampMixin, Base):
    __tablename__ = "sourcing_requests"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    vehicle_make: Mapped[str] = mapped_column(String(100))
    vehicle_model: Mapped[str] = mapped_column(String(100))
    vehicle_year: Mapped[int] = mapped_column(Integer)
    part_name: Mapped[str] = mapped_column(String(200))
    requested_reference: Mapped[str] = mapped_column(String(200))
    quantity: Mapped[int] = mapped_column(Integer)
    max_budget: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    currency: Mapped[str] = mapped_column(String(3))
    needed_by: Mapped[date] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(40), default="request_created")
    selected_quote_id: Mapped[str | None] = mapped_column(String(36), nullable=True)


class SourcingRequestSupplier(Base):
    __tablename__ = "sourcing_request_suppliers"
    __table_args__ = (
        UniqueConstraint("sourcing_request_id", "supplier_id", name="uq_request_supplier"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sourcing_request_id: Mapped[str] = mapped_column(
        ForeignKey("sourcing_requests.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[str] = mapped_column(
        ForeignKey("suppliers.id", ondelete="CASCADE"), index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sourcing_request_id: Mapped[str] = mapped_column(
        ForeignKey("sourcing_requests.id", ondelete="CASCADE"), index=True
    )
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"), index=True)
    exact_reference_confirmed: Mapped[str] = mapped_column(String(10))
    offered_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)
    in_stock: Mapped[str] = mapped_column(String(10))
    manufacturer_or_brand: Mapped[str | None] = mapped_column(String(200), nullable=True)
    condition: Mapped[str] = mapped_column(String(20))
    quantity_available: Mapped[int | None] = mapped_column(Integer, nullable=True)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    tax_included: Mapped[str] = mapped_column(String(10))
    warranty_months: Mapped[int | None] = mapped_column(Integer, nullable=True)
    pickup_available_today: Mapped[str] = mapped_column(String(10))
    delivery_eta: Mapped[str | None] = mapped_column(String(100), nullable=True)
    quote_valid_until: Mapped[str | None] = mapped_column(String(100), nullable=True)
    supplier_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class CallAttempt(TimestampMixin, Base):
    __tablename__ = "call_attempts"
    __table_args__ = (
        CheckConstraint("call_type IN ('quote', 'reservation')", name="ck_call_type"),
        UniqueConstraint(
            "logical_idempotency_key", "attempt_number", name="uq_call_logical_attempt"
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sourcing_request_id: Mapped[str] = mapped_column(ForeignKey("sourcing_requests.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    call_type: Mapped[str] = mapped_column(String(20))
    logical_idempotency_key: Mapped[str] = mapped_column(String(255))
    attempt_number: Mapped[int] = mapped_column(Integer, default=1)
    provider_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(40))


class Reservation(TimestampMixin, Base):
    __tablename__ = "reservations"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending_approval','calling','confirmed','refused',"
            "'unavailable','unclear','no_answer','failed')",
            name="ck_reservation_status",
        ),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sourcing_request_id: Mapped[str] = mapped_column(
        ForeignKey("sourcing_requests.id"), unique=True
    )
    supplier_quote_id: Mapped[str] = mapped_column(ForeignKey("supplier_quotes.id"))
    supplier_id: Mapped[str] = mapped_column(ForeignKey("suppliers.id"))
    status: Mapped[str] = mapped_column(String(30), default="pending_approval")
    provider_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reservation_reference: Mapped[str | None] = mapped_column(String(200), nullable=True)


class AuditEvent(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sourcing_request_id: Mapped[str] = mapped_column(
        ForeignKey("sourcing_requests.id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(60))
    safe_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)


class WebhookReceipt(Base):
    __tablename__ = "webhook_receipts"
    __table_args__ = (
        UniqueConstraint("provider", "provider_event_id", name="uq_provider_event"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    provider: Mapped[str] = mapped_column(String(40))
    provider_event_id: Mapped[str] = mapped_column(String(150))
    provider_call_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payload_hash: Mapped[str] = mapped_column(String(64))
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="received")
