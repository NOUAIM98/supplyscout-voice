from typing import Protocol, Sequence

from ...db.models import SourcingRequest, Supplier, SupplierQuote


class CallProvider(Protocol):
    mode: str

    def suppliers(self) -> Sequence[Supplier]: ...

    def collect_quotes(
        self, sourcing_request: SourcingRequest, suppliers: Sequence[Supplier]
    ) -> list[SupplierQuote]: ...

    def create_quote_call(
        self, sourcing_request: SourcingRequest, supplier: Supplier, *, knowledge_context: str = ""
    ) -> SupplierQuote: ...

    def create_reservation_call(
        self,
        sourcing_request: SourcingRequest,
        selected_quote: SupplierQuote,
        supplier: Supplier,
        *,
        approved: bool = False,
    ) -> dict[str, str | None]: ...
