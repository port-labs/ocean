from asyncio import BoundedSemaphore

from loguru import logger

from gcp_core.errors import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessageError,
)
from gcp_core.feed_event import get_project_name_from_ancestors, parse_asset_data
from gcp_core.helpers.ratelimiter.fixed_window import FixedWindowLimiter
from gcp_core.overrides import ProtoConfig
from gcp_core.search.resource_searches import feed_event_to_resource
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import (
    AbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

rate_limiter: FixedWindowLimiter | None = None
semaphore: BoundedSemaphore | None = None


class AssetFeedProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            await parse_asset_data(event.payload["message"]["data"])
            return True
        except GotFeedCreatedSuccessfullyMessageError:
            logger.info("Assets Feed created successfully")
            return False
        except Exception:
            return False

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        asset_data = await parse_asset_data(event.payload["message"]["data"])
        return [asset_data["asset"]["assetType"]]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "message" in payload and "data" in payload["message"]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        asset_data = await parse_asset_data(payload["message"]["data"])
        asset_type = asset_data["asset"]["assetType"]
        asset_name = asset_data["asset"]["name"]

        try:
            asset_project = get_project_name_from_ancestors(
                asset_data["asset"]["ancestors"]
            )
        except AssetHasNoProjectAncestorError:
            logger.warning(
                f"Couldn't find project ancestor for asset {asset_name}. "
                "Other ancestor types are not supported yet."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = ProtoConfig(
            preserving_proto_field_name=bool(
                getattr(
                    resource_config.selector, "preserve_api_response_case_style", False
                )
            )
        )

        logger.info(
            f"Processing real-time event for {asset_type}: {asset_name} in {asset_project}"
        )

        asset_resource_data = await feed_event_to_resource(
            asset_type,
            asset_name,
            asset_project,
            asset_data,
            rate_limiter,
            semaphore,
            config,
        )

        if asset_data.get("deleted") is True:
            logger.info(f"Resource {asset_type}: {asset_name} deleted in GCP")
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[asset_resource_data],
            )

        logger.info(
            f"Resource {asset_type}: {asset_name} created/updated in {asset_project}"
        )
        return WebhookEventRawResults(
            updated_raw_results=[asset_resource_data],
            deleted_raw_results=[],
        )
