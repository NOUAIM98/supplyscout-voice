from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel


YesNoUnknown = Literal["yes", "no", "unknown"]
Condition = Literal["new", "remanufactured", "used", "other", "unknown"]


class SupplierQuoteRead(BaseModel):
    id: str
    sourcing_request_id: str
    supplier_id: str
    supplier_name: str
    exact_reference_confirmed: YesNoUnknown
    offered_reference: str | None
    in_stock: YesNoUnknown
    manufacturer_or_brand: str | None
    condition: Condition
    quantity_available: int | None
    unit_price: Decimal | None
    currency: str | None
    tax_included: YesNoUnknown
    warranty_months: int | None
    pickup_available_today: YesNoUnknown
    delivery_eta: str | None
    quote_valid_until: str | None
    supplier_notes: str | None
    created_at: datetime


class RankingEntry(BaseModel):
    rank: int
    quote_id: str
    supplier_id: str
    supplier_name: str
    reasons: list[str]


class RankingResponse(BaseModel):
    sourcing_request_id: str
    recommended_supplier_id: str
    recommended_supplier_name: str
    explanation: str
    ranking: list[RankingEntry]


class QuoteSelection(BaseModel):
    quote_id: str
