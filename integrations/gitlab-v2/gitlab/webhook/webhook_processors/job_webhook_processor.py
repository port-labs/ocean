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
from integration import JobResourceConfig
from typing import cast


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

        selector = cast(JobResourceConfig, resource_config).selector
        include_active_projects = selector.include_active_projects

        if include_active_projects is not None:
            project = await self._gitlab_webhook_client.get_project(project_id)
            is_active = not project["archived"]
            if include_active_projects != is_active:
                logger.info(
                    f"Job {job_id} filtered out because project {project_id} "
                    f"is {'archived' if not is_active else 'active'}. Skipping..."
                )
                return WebhookEventRawResults(
                    updated_raw_results=[],
                    deleted_raw_results=[],
                )

        job = await self._gitlab_webhook_client.get_job(project_id, job_id)

        return WebhookEventRawResults(
            updated_raw_results=[job],
            deleted_raw_results=[],
        )
