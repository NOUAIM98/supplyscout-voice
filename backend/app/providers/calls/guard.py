import re

from sqlalchemy.orm import Session

from ...config import Settings
from ...db.models import SourcingRequest, Supplier
from ...db.repositories import AuditRepository, ReservationRepository, SupplierRepository


E164_PATTERN = re.compile(r"\+[1-9]\d{7,14}")


class LiveCallBlocked(PermissionError):
    """A safe, user-displayable live-call authorization failure."""


def mask_phone(phone: str) -> str:
    return f"{phone[:3]}******{phone[-3:]}" if len(phone) >= 7 else "***"


def assert_live_call_allowed(
    session: Session,
    settings: Settings,
    request: SourcingRequest,
    supplier: Supplier,
    action_type: str,
) -> None:
    if settings.call_provider_mode != "calle":
        raise LiveCallBlocked("Live call provider is not selected")
    if not settings.calle_live_enabled:
        raise LiveCallBlocked("Live calls are disabled")
    if E164_PATTERN.fullmatch(supplier.phone_e164) is None:
        raise LiveCallBlocked("Supplier phone is not valid E.164")
    if supplier.phone_e164 not in settings.allowed_calle_recipients:
        raise LiveCallBlocked("Supplier recipient is not allowlisted")
    if not settings.calle_recipient_region or not settings.calle_recipient_locale:
        raise LiveCallBlocked("CALL-E recipient region and locale are required")
    if not supplier.authorized_for_calls:
        raise LiveCallBlocked("Supplier is not approved for calls")
    assigned = {item.id for item in SupplierRepository(session).assigned_to(request.id)}
    if supplier.id not in assigned:
        raise LiveCallBlocked("Supplier is not assigned to this sourcing request")
    audit = AuditRepository(session)
    if action_type == "quote":
        if not audit.exists(request.id, "quote_calls_approved"):
            raise LiveCallBlocked("Persisted quote-call approval is required")
        return
    if action_type != "reservation":
        raise LiveCallBlocked("Unsupported live call action")
    reservation = ReservationRepository(session).for_request(request.id)
    if (
        request.selected_quote_id is None
        or reservation is None
        or reservation.supplier_id != supplier.id
        or not audit.exists(request.id, "reservation_approved")
    ):
        raise LiveCallBlocked("Separate persisted reservation approval is required")
