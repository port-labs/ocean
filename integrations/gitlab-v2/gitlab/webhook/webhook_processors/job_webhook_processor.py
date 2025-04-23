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


class JobWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["build"]
    hooks = ["Job Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.JOB]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        job_id = payload["build_id"]
        project_id = payload["project"]["id"]
        logger.info(
            f"Handling job webhook event for project {project_id} and job {job_id}"
        )

        job = await self._gitlab_webhook_client.get_job(project_id, job_id)

        return WebhookEventRawResults(
            updated_raw_results=[job],
            deleted_raw_results=[],
        )
