from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence
from uuid import NAMESPACE_URL, uuid5

from ...db.models import SourcingRequest, Supplier, SupplierQuote


REFERENCE = "TEST-ALT-CLIO-2019-001"


class FakeCallProvider:
    mode = "fake"

    def suppliers(self) -> Sequence[Supplier]:
        return (
            self._supplier("A", "+12025550101"),
            self._supplier("B", "+12025550102"),
            self._supplier("C", "+12025550103"),
        )

    def collect_quotes(
        self, sourcing_request: SourcingRequest, suppliers: Sequence[Supplier]
    ) -> list[SupplierQuote]:
        return [
            self.create_quote_call(sourcing_request, supplier)
            for supplier in suppliers
        ]

    def create_quote_call(
        self, sourcing_request: SourcingRequest, supplier: Supplier
    ) -> SupplierQuote:
        fixtures = self._quote_fixtures()
        return SupplierQuote(
            id=str(uuid5(NAMESPACE_URL, f"{sourcing_request.id}:{supplier.id}")),
            sourcing_request_id=sourcing_request.id,
            supplier_id=supplier.id,
            created_at=datetime.now(timezone.utc),
            **fixtures[supplier.name],
        )

    def create_reservation_call(
        self,
        sourcing_request: SourcingRequest,
        selected_quote: SupplierQuote,
        supplier: Supplier,
        *,
        approved: bool = False,
    ) -> dict[str, str | None]:
        if not approved:
            raise PermissionError("Explicit reservation approval is required")
        if selected_quote.sourcing_request_id != sourcing_request.id:
            raise ValueError("Selected quote does not belong to the sourcing request")
        if selected_quote.supplier_id != supplier.id:
            raise ValueError("Selected quote does not belong to the supplier")
        return {
            "outcome": "confirmed",
            "supplier_reference": f"FAKE-RES-{supplier.name[-1]}-001",
        }

    @staticmethod
    def _quote_fixtures() -> dict[str, dict[str, object]]:
        return {
            "Supplier A": {
                "exact_reference_confirmed": "yes",
                "offered_reference": REFERENCE,
                "in_stock": "yes",
                "manufacturer_or_brand": "Demo Brand A",
                "condition": "new",
                "quantity_available": 1,
                "unit_price": Decimal("145.00"),
                "currency": "EUR",
                "tax_included": "unknown",
                "warranty_months": 12,
                "pickup_available_today": "yes",
                "delivery_eta": None,
                "quote_valid_until": None,
                "supplier_notes": "Exact reference available for pickup today.",
            },
            "Supplier B": {
                "exact_reference_confirmed": "yes",
                "offered_reference": REFERENCE,
                "in_stock": "yes",
                "manufacturer_or_brand": "Demo Brand B",
                "condition": "new",
                "quantity_available": 1,
                "unit_price": Decimal("132.00"),
                "currency": "EUR",
                "tax_included": "unknown",
                "warranty_months": 12,
                "pickup_available_today": "no",
                "delivery_eta": "tomorrow",
                "quote_valid_until": None,
                "supplier_notes": "Delivery is available tomorrow.",
            },
            "Supplier C": {
                "exact_reference_confirmed": "unknown",
                "offered_reference": None,
                "in_stock": "yes",
                "manufacturer_or_brand": None,
                "condition": "unknown",
                "quantity_available": None,
                "unit_price": Decimal("118.00"),
                "currency": "EUR",
                "tax_included": "unknown",
                "warranty_months": 6,
                "pickup_available_today": "yes",
                "delivery_eta": None,
                "quote_valid_until": None,
                "supplier_notes": "Exact reference could not be confirmed.",
            },
        }

    @staticmethod
    def _supplier(label: str, phone_e164: str) -> Supplier:
        name = f"Supplier {label}"
        now = datetime.now(timezone.utc)
        return Supplier(
            id=str(uuid5(NAMESPACE_URL, f"supplyscout:{name}")),
            name=name,
            phone_e164=phone_e164,
            authorized_for_calls=True,
            created_at=now,
            updated_at=now,
        )
