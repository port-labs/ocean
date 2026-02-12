from typing import cast

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
from integration import ProjectResourceConfig
from loguru import logger


class PushWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PROJECT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project"]["id"]
        logger.info(f"Handling push webhook event for project with ID '{project_id}'")

        selector = cast(ProjectResourceConfig, resource_config).selector
        included_files = selector.included_files or []
        project = await self._gitlab_webhook_client.get_project(
            project_id,
            included_files=included_files if included_files else None,
        )

        return WebhookEventRawResults(
            updated_raw_results=[project], deleted_raw_results=[]
        )
