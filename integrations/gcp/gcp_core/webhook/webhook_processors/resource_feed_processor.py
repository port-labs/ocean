from loguru import logger

from gcp_core.errors import AssetHasNoProjectAncestorError
from gcp_core.feed_event import FeedContent, get_project_name_from_ancestors
from gcp_core.overrides import ProtoConfig
from gcp_core.search.resource_searches import feed_event_to_resource
from gcp_core.utils import resolve_request_controllers
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from gcp_core.webhook.webhook_processors.base_webhook_processor import (
    BaseWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class ResourceFeedProcessor(BaseWebhookProcessor):
    feed_content = FeedContent.RESOURCE

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        feed_event = await self._get_feed_event(event.payload)
        if feed_event is None:
            return []

        # The manager pairs each kind returned here with every resource of that kind in the
        # mapping, so narrowing it against the mapping again would repeat the event per resource.
        return [feed_event.asset.asset_type]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        feed_event = await self._get_feed_event(payload)
        if feed_event is None:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        asset_type = feed_event.asset.asset_type
        asset_name = feed_event.asset.name

        try:
            asset_project = get_project_name_from_ancestors(feed_event.asset.ancestors)
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
            feed_event,
            rate_limiter,
            semaphore,
            config,
        )

        if feed_event.deleted:
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
