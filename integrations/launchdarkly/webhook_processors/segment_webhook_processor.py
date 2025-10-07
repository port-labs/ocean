from webhook_processors.launchdarkly_abstract_webhook_processor import (
    _LaunchDarklyAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from client import LaunchDarklyClient, ObjectKind
from loguru import logger
from webhook_processors.utils import (
    enrich_resource_with_project,
)


class SegmentWebhookProcessor(_LaunchDarklyAbstractWebhookProcessor):
    """Processes segment-related webhook events from LaunchDarkly."""

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        """Validate that the event header contains required Segment event type."""
        logger.info(
            f"SegmentWebhookProcessor checking event: kind={event.payload.get('kind')}, ObjectKind.SEGMENT={ObjectKind.SEGMENT}"
        )
        return event.payload.get("kind") == ObjectKind.SEGMENT

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SEGMENT]

    async def handle_event(
        self, payload: EventPayload, resource: ResourceConfig
    ) -> WebhookEventRawResults:
        logger.info(f"Processing segment webhook event: {payload.get('kind')}")

        target = payload.get("target", {})
        current_version = payload.get("currentVersion", {})

        segment_key = None
        project_key = None
        environment_key = None

        if target and "resources" in target:
            resource_str = target["resources"][0] if target["resources"] else ""
            if ":" in resource_str:
                parts = resource_str.split(":")
                if len(parts) >= 3:
                    project_part = parts[0].replace("proj/", "")
                    env_part = parts[1].replace("env/", "")
                    segment_part = parts[2].replace("segment/", "").split(";")[0]

                    project_key = project_part
                    environment_key = env_part
                    segment_key = segment_part

        if not segment_key and payload.get("_links", {}).get("site", {}).get("href"):
            site_href = payload["_links"]["site"]["href"]
            if "/segments/" in site_href:
                segment_key = site_href.split("/segments/")[-1]
                path_parts = site_href.split("/")
                if len(path_parts) >= 3:
                    project_key = path_parts[1]
                    environment_key = path_parts[2]

        if not segment_key:
            logger.error("Could not extract segment key from webhook payload")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            f"Processing segment: {segment_key} in project: {project_key}, environment: {environment_key}"
        )

        if self.is_deletion_event(payload):
            deleted_segment = {
                "key": segment_key,
                "__projectKey": project_key,
                "__environmentKey": environment_key,
                "deleted": True,
            }
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[deleted_segment]
            )

        if current_version:
            segment_data = current_version.copy()
            segment_data["key"] = segment_key
            segment_data["__projectKey"] = project_key
            segment_data["__environmentKey"] = environment_key

            segment_data["__webhookEventId"] = payload.get("_id")
            segment_data["__webhookDate"] = payload.get("date")
            segment_data["__webhookAction"] = payload.get("titleVerb", "")

            return WebhookEventRawResults(
                updated_raw_results=[segment_data], deleted_raw_results=[]
            )

        try:
            client = LaunchDarklyClient.create_from_ocean_configuration()
            endpoint = f"segments/{project_key}/{environment_key}/{segment_key}"
            segment_data = await enrich_resource_with_project(
                endpoint, ObjectKind.SEGMENT, client
            )
            segment_data["__environmentKey"] = environment_key

            return WebhookEventRawResults(
                updated_raw_results=[segment_data], deleted_raw_results=[]
            )
        except Exception as e:
            logger.error(f"Failed to fetch segment data from API: {e}")
            basic_segment = {
                "key": segment_key,
                "__projectKey": project_key,
                "__environmentKey": environment_key,
                "name": target.get("name", segment_key),
                "__webhookEventId": payload.get("_id"),
                "__webhookDate": payload.get("date"),
                "__webhookAction": payload.get("titleVerb", ""),
            }
            return WebhookEventRawResults(
                updated_raw_results=[basic_segment], deleted_raw_results=[]
            )
