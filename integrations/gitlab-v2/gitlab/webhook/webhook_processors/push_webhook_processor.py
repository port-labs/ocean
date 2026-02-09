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
from typing import cast
from integration import ProjectResourceConfig


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
        search_queries = (
            [sq.dict() for sq in selector.search_queries]
            if selector.search_queries
            else None
        )
        project = await self._gitlab_webhook_client.get_project(
            project_id,
            search_queries=search_queries,
        )

        return WebhookEventRawResults(
            updated_raw_results=[project], deleted_raw_results=[]
        )
