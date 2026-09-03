from dataclasses import dataclass
from datetime import date, timedelta
from decimal import Decimal

from ..db.models import SourcingRequest, Supplier, SupplierQuote


@dataclass(frozen=True)
class RankedQuote:
    quote: SupplierQuote
    supplier: Supplier
    reasons: list[str]


def rank_quotes(
    sourcing_request: SourcingRequest,
    quotes: list[SupplierQuote],
    suppliers: dict[str, Supplier],
) -> list[RankedQuote]:
    ordered = sorted(
        quotes,
        key=lambda quote: (
            {"yes": 0, "unknown": 1, "no": 2}[quote.exact_reference_confirmed],
            _deadline_rank(sourcing_request, quote),
            _price_rank(sourcing_request, quote),
            -(quote.warranty_months or 0),
            quote.id,
        ),
    )
    return [
        RankedQuote(
            quote=quote,
            supplier=suppliers[quote.supplier_id],
            reasons=_explain(sourcing_request, quote),
        )
        for quote in ordered
    ]


def _fulfillment_date(quote: SupplierQuote) -> date | None:
    today = date.today()
    if quote.pickup_available_today == "yes":
        return today
    if quote.delivery_eta:
        eta = quote.delivery_eta.strip().lower()
        if eta == "today":
            return today
        if eta == "tomorrow":
            return today + timedelta(days=1)
    return None


def _deadline_rank(sourcing_request: SourcingRequest, quote: SupplierQuote) -> int:
    fulfillment = _fulfillment_date(quote)
    if fulfillment is None:
        return 2
    return 0 if fulfillment <= sourcing_request.needed_by else 1


def _price_rank(
    sourcing_request: SourcingRequest, quote: SupplierQuote
) -> Decimal:
    if quote.unit_price is None or quote.currency != sourcing_request.currency:
        return Decimal("Infinity")
    return quote.unit_price


def _explain(sourcing_request: SourcingRequest, quote: SupplierQuote) -> list[str]:
    reasons = []
    if quote.exact_reference_confirmed == "yes":
        reasons.append("Exact requested reference confirmed.")
    elif quote.exact_reference_confirmed == "unknown":
        reasons.append("Exact requested reference is not confirmed.")
    else:
        reasons.append("Exact requested reference was not available.")

    deadline_rank = _deadline_rank(sourcing_request, quote)
    if deadline_rank == 0:
        reasons.append("Meets the required deadline.")
    elif deadline_rank == 1:
        reasons.append("Misses the required deadline.")
    else:
        reasons.append("Deadline satisfaction is unknown.")

    if quote.unit_price is None or quote.currency != sourcing_request.currency:
        reasons.append("Price is not directly comparable.")
    elif quote.unit_price <= sourcing_request.max_budget:
        reasons.append(f"Price is under the {sourcing_request.max_budget} {sourcing_request.currency} budget.")
    else:
        reasons.append(f"Price exceeds the {sourcing_request.max_budget} {sourcing_request.currency} budget.")

    if quote.warranty_months is None:
        reasons.append("Warranty is unknown.")
    else:
        reasons.append(f"Includes a {quote.warranty_months}-month warranty.")
    return reasons
