from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from gitlab.helpers.utils import ObjectKind
from loguru import logger


class ReleaseWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["release"]
    hooks = ["Release Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.RELEASE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project"]["id"]
        tag_name = payload["tag"]
        project_path = payload["project"]["path_with_namespace"]
        logger.info(
            f"Handling release webhook event for project with ID '{project_id} and tag name '{tag_name}'"
        )
        if payload["action"] == "delete":
            release = self._gitlab_webhook_client.enrich_with_project_path(
                payload, project_path
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[release]
            )

        release = await self._gitlab_webhook_client.get_release(
            project_id=project_id,
            tag_name=tag_name,
        )
        if release:
            release = self._gitlab_webhook_client.enrich_with_project_path(
                release, project_path
            )
            return WebhookEventRawResults(
                updated_raw_results=[release], deleted_raw_results=[]
            )

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
