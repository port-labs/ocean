from typing import Any

from loguru import logger

from gcp_core.errors import GotFeedCreatedSuccessfullyMessageError
from gcp_core.feed_event import parse_asset_data
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
)


class BaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for all GCP webhook processors."""

    _cached_asset_data: dict[str, Any] | None = None

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _get_parsed_event(self, payload: EventPayload) -> dict[str, Any] | None:
        if self._cached_asset_data is not None:
            return self._cached_asset_data

        if (
            not isinstance(payload.get("message"), dict)
            or "data" not in payload["message"]
        ):
            return None

        try:
            parsed_data = await parse_asset_data(payload["message"]["data"])
            self._cached_asset_data = parsed_data
            return parsed_data
        except GotFeedCreatedSuccessfullyMessageError:
            logger.info("Assets Feed created successfully")
            return None
        except Exception as e:
            logger.warning(f"Failed to process asset feed event: {e}")
            return None
