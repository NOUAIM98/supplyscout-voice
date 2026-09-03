from typing import Protocol, Sequence

from ...db.models import SourcingRequest, Supplier, SupplierQuote


class CallProvider(Protocol):
    mode: str

    def suppliers(self) -> Sequence[Supplier]: ...

    def collect_quotes(
        self, sourcing_request: SourcingRequest, suppliers: Sequence[Supplier]
    ) -> list[SupplierQuote]: ...
