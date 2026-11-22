import binascii
import json
from typing import ClassVar

from loguru import logger
from pydantic import ValidationError

from gcp_core.errors import GotFeedCreatedSuccessfullyMessageError
from gcp_core.feed_event import FeedContent, FeedEvent, parse_feed_event
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
)


class BaseWebhookProcessor(AbstractWebhookProcessor):
    """Base class for all GCP webhook processors: one per feed content type.

    Every Cloud Asset Inventory feed publishes to the same `/events` path, so the processor that
    handles a given event is the one whose `feed_content` the event carries.
    """

    feed_content: ClassVar[FeedContent]

    _cached_feed_event: FeedEvent | None = None

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def _get_feed_event(self, payload: EventPayload) -> FeedEvent | None:
        if self._cached_feed_event is not None:
            return self._cached_feed_event

        if (
            not isinstance(payload.get("message"), dict)
            or "data" not in payload["message"]
        ):
            return None

        try:
            self._cached_feed_event = await parse_feed_event(payload["message"]["data"])
            return self._cached_feed_event
        except GotFeedCreatedSuccessfullyMessageError:
            logger.info("Assets Feed created successfully")
            return None
        except (binascii.Error, json.JSONDecodeError, ValidationError) as e:
            # Named, because an unreadable message and a content type we do not consume both end
            # in a declined event: only this log says which one happened.
            logger.warning(f"Could not read the feed event, skipping it: {e}")
            return None
        except Exception:
            logger.exception("Unexpected failure reading a feed event, skipping it")
            return None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        feed_event = await self._get_feed_event(event.payload)
        if feed_event is None:
            return False

        if feed_event.content is None:
            # Core reports this as an unknown webhook event, naming neither GCP nor the feed.
            logger.debug(
                f"Feed event for asset '{feed_event.asset.name}' carries no content type this "
                "integration consumes; check what the feeds on this topic publish."
            )
            return False

        return feed_event.content is self.feed_content

    async def validate_payload(self, payload: EventPayload) -> bool:
        feed_event = await self._get_feed_event(payload)
        if feed_event is None:
            return False

        # Both handle_event implementations read these off the asset with nothing to fall back
        # on. `ancestors` is not here: an asset with no project ancestor is unsupported rather
        # than malformed, and handle_event already logs and skips it.
        missing = [
            field
            for field, value in (
                ("name", feed_event.asset.name),
                ("assetType", feed_event.asset.asset_type),
            )
            if not value
        ]
        if missing:
            logger.warning(
                f"Skipping {self.feed_content} feed event for asset "
                f"'{feed_event.asset.name}': missing {', '.join(missing)}"
            )
            return False
        return True
