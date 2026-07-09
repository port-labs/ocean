from typing import Any, cast

from loguru import logger

from gcp_core.errors import (
    AssetHasNoProjectAncestorError,
    GotFeedCreatedSuccessfullyMessageError,
)
from gcp_core.feed_event import get_project_name_from_ancestors, parse_asset_data
from gcp_core.overrides import GCPPortAppConfig, ProtoConfig
from gcp_core.search.resource_searches import feed_event_to_resource
from gcp_core.utils import resolve_request_controllers
from port_ocean.context.event import event as port_event
from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from gcp_core.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class AssetFeedProcessor(BaseWebhookProcessor):
    _cached_asset_data: dict[str, Any] | None = None

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

    async def should_process_event(self, event: WebhookEvent) -> bool:
        if ocean.event_listener_type == "ONCE":
            return False

        asset_data = await self._get_parsed_event(event.payload)
        return asset_data is not None

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        asset_data = await self._get_parsed_event(event.payload)
        if not asset_data:
            return []

        asset_type = asset_data["asset"]["assetType"]
        resource_configs = cast(GCPPortAppConfig, port_event.port_app_config).resources

        return [config.kind for config in resource_configs if config.kind == asset_type]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        asset_data = await self._get_parsed_event(payload)
        return asset_data is not None

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        asset_data = await self._get_parsed_event(payload)
        if not asset_data:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

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
        rate_limiter, semaphore = await resolve_request_controllers(asset_type)
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
