from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field


class SourcingRequestCreate(BaseModel):
    vehicle_make: str = Field(min_length=1, max_length=100)
    vehicle_model: str = Field(min_length=1, max_length=100)
    vehicle_year: int = Field(ge=1886, le=2100)
    part_name: str = Field(min_length=1, max_length=200)
    requested_reference: str = Field(min_length=1, max_length=200)
    quantity: int = Field(gt=0)
    max_budget: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(min_length=3, max_length=3)
    needed_by: date


class SourcingRequestRead(SourcingRequestCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    status: str
    created_at: datetime
    updated_at: datetime
