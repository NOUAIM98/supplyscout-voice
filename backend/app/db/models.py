from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utc_now


class Supplier(Base):
    __tablename__ = "suppliers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    phone_e164: Mapped[str] = mapped_column(String(16), unique=True)
    authorized_for_calls: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SourcingRequest(Base):
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
    status: Mapped[str] = mapped_column(String(40), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )


class SupplierQuote(Base):
    __tablename__ = "supplier_quotes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    sourcing_request_id: Mapped[str] = mapped_column(
        ForeignKey("sourcing_requests.id"), index=True
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
