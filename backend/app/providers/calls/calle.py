import re
import ssl
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import NAMESPACE_URL, uuid5

import httpx
from calle import CalleClient

from ...db.models import SourcingRequest, Supplier, SupplierQuote


E164_PATTERN = re.compile(r"\+[1-9]\d{7,14}")

CALLE_QUOTE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "description": "Factual supplier quote details; omitted fields were not established.",
    "additionalProperties": False,
    "properties": {
        "exact_reference_confirmed": {
            "type": "string",
            "enum": ["yes", "no", "unknown"],
        },
        "offered_reference": {"type": "string"},
        "in_stock": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "manufacturer_or_brand": {"type": "string"},
        "condition": {
            "type": "string",
            "enum": ["new", "remanufactured", "used", "other", "unknown"],
        },
        "quantity_available": {"type": "integer"},
        "unit_price": {"type": "number"},
        "currency": {"type": "string"},
        "tax_included": {"type": "string", "enum": ["yes", "no", "unknown"]},
        "warranty_months": {"type": "integer"},
        "pickup_available_today": {
            "type": "string",
            "enum": ["yes", "no", "unknown"],
        },
        "delivery_eta": {"type": "string"},
        "quote_valid_until": {"type": "string"},
        "supplier_notes": {"type": "string"},
    },
    "required": [
        "exact_reference_confirmed",
        "in_stock",
        "condition",
        "tax_included",
        "pickup_available_today",
    ],
}

CALLE_RESERVATION_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "outcome": {
            "type": "string",
            "enum": [
                "confirmed",
                "refused",
                "unavailable",
                "unclear",
                "no_answer",
                "failed",
            ],
        },
        "supplier_reference": {"type": "string"},
    },
    "required": ["outcome"],
}


class CalleResultError(RuntimeError):
    """Raised when CALL-E returns no usable structured supplier result."""


class CalleCallProvider:
    mode = "calle"

    def __init__(
        self,
        *,
        api_key: str,
        base_url: str = "https://api.heycall-e.com",
        recipients: Mapping[str, dict[str, Any]] | None = None,
        client: Any | None = None,
    ) -> None:
        if not api_key:
            raise RuntimeError("CALLE_API_KEY is required when CALL_PROVIDER_MODE=calle")
        self._api_key = api_key
        self._base_url = base_url
        self._recipients = dict(recipients or {})
        self._client_instance = client
        self.provider_results: dict[str, dict[str, Any]] = {}

    def suppliers(self) -> Sequence[Supplier]:
        return ()

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
        response = self.start_quote_call(sourcing_request, supplier)
        return self.normalize_quote_response(response, sourcing_request, supplier)

    def start_quote_call(
        self, sourcing_request: SourcingRequest, supplier: Supplier
    ) -> dict[str, Any]:
        request = self.build_quote_request(sourcing_request, supplier)
        return self._client().calls.create(**request)

    def build_quote_request(
        self, sourcing_request: SourcingRequest, supplier: Supplier
    ) -> dict[str, Any]:
        """Build and validate SDK arguments without creating a CALL-E call."""
        recipient = self._validated_recipient(supplier)
        return {
            "task": self._quote_task(sourcing_request, recipient["locale"]),
            "recipient": recipient,
            "recipient_result_schema": CALLE_QUOTE_SCHEMA,
            "metadata": {
                "workflow_type": "supplier_quote",
                "sourcing_request_id": sourcing_request.id,
                "supplier_id": supplier.id,
            },
            "idempotency_key": self.quote_idempotency_key(
                sourcing_request.id, supplier.id
            ),
        }

    def get_quote_result(
        self, call_id: str, sourcing_request: SourcingRequest, supplier: Supplier
    ) -> SupplierQuote:
        response = self.get_call(call_id)
        return self.normalize_quote_response(response, sourcing_request, supplier)

    def get_call(self, call_id: str) -> dict[str, Any]:
        return self._client().calls.get(call_id)

    def list_goals(self, *, limit: int = 1) -> dict[str, Any]:
        """Perform an authenticated, read-only connectivity check."""
        return self._client().goals.list(limit=limit)

    def list_events(
        self, call_id: str, *, cursor: str | None = None, limit: int | None = None
    ) -> dict[str, Any]:
        return self._client().calls.list_events(call_id, cursor=cursor, limit=limit)

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
        recipient = self._validated_recipient(supplier)
        response = self._client().calls.create(
            task=self._reservation_task(sourcing_request, selected_quote),
            recipient=recipient,
            recipient_result_schema=CALLE_RESERVATION_SCHEMA,
            metadata={
                "workflow_type": "supplier_reservation",
                "sourcing_request_id": sourcing_request.id,
                "supplier_id": supplier.id,
            },
            idempotency_key=(
                f"supplyscout:reservation:{sourcing_request.id}:{selected_quote.id}"
            ),
        )
        structured = self._structured_result(response)
        if not isinstance(structured, dict):
            return {"outcome": "failed", "supplier_reference": None}
        outcome = structured.get("outcome")
        if outcome not in CALLE_RESERVATION_SCHEMA["properties"]["outcome"]["enum"]:
            outcome = "unclear"
        reference = structured.get("supplier_reference")
        return {
            "outcome": outcome,
            "supplier_reference": reference if isinstance(reference, str) else None,
        }

    @staticmethod
    def quote_idempotency_key(sourcing_request_id: str, supplier_id: str) -> str:
        return f"supplyscout:quote:{sourcing_request_id}:{supplier_id}"

    def normalize_quote_response(
        self,
        response: dict[str, Any],
        sourcing_request: SourcingRequest,
        supplier: Supplier,
    ) -> SupplierQuote:
        provider_result = self._provider_result(response)
        self.provider_results[supplier.id] = provider_result
        structured = self._structured_result(response)
        if not isinstance(structured, dict):
            raise CalleResultError("CALL-E returned no structured recipient result")
        try:
            values = self._normalize_quote_values(structured)
            return SupplierQuote(
                id=str(
                    uuid5(
                        NAMESPACE_URL,
                        f"calle:{response.get('id', '')}:{sourcing_request.id}:{supplier.id}",
                    )
                ),
                sourcing_request_id=sourcing_request.id,
                supplier_id=supplier.id,
                created_at=datetime.now(timezone.utc),
                **values,
            )
        except (TypeError, ValueError, InvalidOperation) as exc:
            raise CalleResultError("CALL-E returned an invalid structured result") from exc

    def _client(self) -> Any:
        if self._client_instance is None:
            ssl_context = ssl.create_default_context()
            if (
                not ssl_context.check_hostname
                or ssl_context.verify_mode != ssl.CERT_REQUIRED
            ):
                raise RuntimeError("TLS certificate verification is not enabled")
            http_client = httpx.Client(
                base_url=self._base_url.rstrip("/"),
                headers={"Authorization": f"Bearer {self._api_key}"},
                timeout=httpx.Timeout(30.0, connect=10.0),
                verify=ssl_context,
            )
            self._client_instance = CalleClient(
                api_key=self._api_key,
                http_client=http_client,
            )
        return self._client_instance

    def close(self) -> None:
        if self._client_instance is not None:
            self._client_instance._client.close()

    def _validated_recipient(self, supplier: Supplier) -> dict[str, Any]:
        if not supplier.authorized_for_calls:
            raise PermissionError("Supplier is not authorized for calls")
        recipient = self._recipients.get(supplier.id)
        if not recipient:
            raise PermissionError("No authorized CALL-E recipient is configured")
        phones = recipient.get("phones")
        region = recipient.get("region")
        locale = recipient.get("locale")
        if (
            not isinstance(phones, list)
            or len(phones) != 1
            or not isinstance(phones[0], str)
            or E164_PATTERN.fullmatch(phones[0]) is None
        ):
            raise ValueError("CALL-E recipient must contain one valid E.164 phone")
        if not isinstance(region, str) or not region:
            raise ValueError("CALL-E recipient region is required")
        if not isinstance(locale, str) or not locale:
            raise ValueError("CALL-E recipient locale is required")
        return {"phones": [phones[0]], "region": region, "locale": locale}

    @staticmethod
    def _structured_result(response: dict[str, Any]) -> Any:
        recipients = response.get("recipients")
        if not isinstance(recipients, list) or not recipients:
            return None
        recipient = recipients[0]
        return recipient.get("structured_result") if isinstance(recipient, dict) else None

    @staticmethod
    def _provider_result(response: dict[str, Any]) -> dict[str, Any]:
        recipients = response.get("recipients")
        recipient = recipients[0] if isinstance(recipients, list) and recipients else {}
        if not isinstance(recipient, dict):
            recipient = {}

        def recipient_or_call(name: str) -> Any:
            value = recipient.get(name)
            return response.get(name) if value is None else value

        return {
            "call_id": response.get("id"),
            "status": response.get("status"),
            "task_completed": recipient_or_call("task_completed"),
            "completion_confidence": recipient_or_call("completion_confidence"),
            "evidence": recipient_or_call("evidence"),
            "failure_code": recipient_or_call("failure_code"),
            "failure_message": recipient_or_call("failure_message"),
        }

    @staticmethod
    def _normalize_quote_values(result: dict[str, Any]) -> dict[str, Any]:
        yes_no_unknown = {"yes", "no", "unknown"}
        conditions = {"new", "remanufactured", "used", "other", "unknown"}

        def enum_value(name: str, allowed: set[str], default: str) -> str:
            value = result.get(name)
            return value if value in allowed else default

        def optional(name: str, expected: type) -> Any:
            value = result.get(name)
            return value if isinstance(value, expected) and not isinstance(value, bool) else None

        price = result.get("unit_price")
        unit_price = None
        if isinstance(price, (int, float, str)) and not isinstance(price, bool):
            unit_price = Decimal(str(price))
        return {
            "exact_reference_confirmed": enum_value(
                "exact_reference_confirmed", yes_no_unknown, "unknown"
            ),
            "offered_reference": optional("offered_reference", str),
            "in_stock": enum_value("in_stock", yes_no_unknown, "unknown"),
            "manufacturer_or_brand": optional("manufacturer_or_brand", str),
            "condition": enum_value("condition", conditions, "unknown"),
            "quantity_available": optional("quantity_available", int),
            "unit_price": unit_price,
            "currency": optional("currency", str),
            "tax_included": enum_value("tax_included", yes_no_unknown, "unknown"),
            "warranty_months": optional("warranty_months", int),
            "pickup_available_today": enum_value(
                "pickup_available_today", yes_no_unknown, "unknown"
            ),
            "delivery_eta": optional("delivery_eta", str),
            "quote_valid_until": optional("quote_valid_until", str),
            "supplier_notes": optional("supplier_notes", str),
        }

    @staticmethod
    def _quote_task(request: SourcingRequest, locale: str) -> str:
        if locale == "fr-FR":
            return (
                "Conduisez entièrement cet appel en français. Commencez exactement par : "
                "« Bonjour. Je suis l’assistant vocal IA SupplyScout, et j’appelle dans "
                "le cadre d’un test autorisé pour obtenir un devis de pièce automobile. "
                "Êtes-vous d’accord pour continuer ? » Si la personne refuse ou ne donne "
                "pas son consentement, terminez poliment l’appel sans poser de questions "
                "d’approvisionnement. Si elle accepte, demandez un devis pour "
                f"{request.quantity} {request.part_name} pour une {request.vehicle_make} "
                f"{request.vehicle_model} {request.vehicle_year}, référence exacte "
                f"{request.requested_reference}, nécessaire aujourd’hui, budget maximal "
                f"{request.max_budget} {request.currency}. Recueillez : confirmation de la "
                "référence exacte, stock, autre référence proposée, fabricant ou marque, "
                "état, quantité disponible, prix unitaire, devise, taxes incluses ou non, "
                "garantie, retrait aujourd’hui, délai de livraison, validité du devis et "
                "notes du fournisseur. Posez de brèves questions de suivi en cas d’ambiguïté. "
                "Préservez l’incertitude et n’inventez aucun fait. Ne commandez, n’achetez, "
                "ne payez, ne réservez et ne prenez aucun engagement. Terminez poliment "
                "après avoir recueilli les informations du devis."
            )
        return (
            "Identify yourself as an AI assistant calling on behalf of an auto repair "
            f"shop. Collect a factual quote for {request.quantity} {request.part_name} "
            f"for a {request.vehicle_year} {request.vehicle_make} {request.vehicle_model}, "
            f"exact requested reference {request.requested_reference}, needed by "
            f"{request.needed_by.isoformat()}, with maximum budget "
            f"{request.max_budget} {request.currency}. Preserve uncertainty and never "
            "guess. Quote collection only: do not order, purchase, pay, reserve, or commit."
        )

    @staticmethod
    def _reservation_task(
        request: SourcingRequest, selected_quote: SupplierQuote
    ) -> str:
        return (
            "Identify yourself as an AI assistant calling on behalf of an auto repair "
            f"shop. Refer only to the human-selected quote for {request.part_name}, "
            f"reference {request.requested_reference}, quoted at "
            f"{selected_quote.unit_price} {selected_quote.currency}. Confirm availability "
            "and request reservation only. Never purchase, pay, or expand scope. Preserve "
            "uncertainty and allow refusal."
        )
