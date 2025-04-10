from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)


class IssueWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["issue"]
    hooks = ["Issue Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ISSUE]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        issue_id = payload["object_attributes"]["iid"]
        project_id = payload["project"]["id"]
        logger.info(
            f"Handling issue webhook event for project {project_id} and issue {issue_id}"
        )

        issue = await self._gitlab_webhook_client.get_issue(project_id, issue_id)

        return WebhookEventRawResults(
            updated_raw_results=[issue],
            deleted_raw_results=[],
        )
