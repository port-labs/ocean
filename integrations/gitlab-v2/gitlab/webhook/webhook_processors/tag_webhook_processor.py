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


class TagWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["tag_push"]
    hooks = ["Tag Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.TAG]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project"]["id"]
        tag_name = payload["ref"].split("/")[-1]
        logger.info(
            f"Handling tag webhook event for project with ID '{project_id}' and tag name '{tag_name}'"
        )
        tag = await self._gitlab_webhook_client.get_tag(
            project_id=project_id,
            tag_name=tag_name,
        )

        if tag:
            project_path = payload["project"]["path_with_namespace"]
            tag = {**tag, "__project": {"path_with_namespace": project_path}}

        return WebhookEventRawResults(updated_raw_results=[tag], deleted_raw_results=[])
