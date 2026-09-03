from collections.abc import Mapping
from typing import Any

from ...config import Settings
from .base import CallProvider
from .calle import CalleCallProvider
from .fake import FakeCallProvider


def create_call_provider(
    settings: Settings,
    *,
    recipients: Mapping[str, dict[str, Any]] | None = None,
    client: Any | None = None,
) -> CallProvider:
    if settings.call_provider_mode == "fake":
        return FakeCallProvider()
    if not settings.calle_api_key:
        raise RuntimeError("CALLE_API_KEY is required when CALL_PROVIDER_MODE=calle")
    return CalleCallProvider(
        api_key=settings.calle_api_key,
        base_url=settings.calle_base_url,
        recipients=recipients,
        client=client,
    )
