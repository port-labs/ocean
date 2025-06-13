from loguru import logger
from github.webhook.events import DEPENDABOT_ACTION_TO_STATE
from github.helpers.utils import ObjectKind, enrich_with_repository
from github.clients.client_factory import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleDependabotAlertOptions
from github.core.exporters.dependabot_exporter import RestDependabotAlertExporter
from typing import cast
from integration import GithubDependabotAlertConfig
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)


class DependabotAlertWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "alert" in payload and "number" in payload["alert"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "dependabot_alert"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DEPENDABOT_ALERT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        alert = payload["alert"]
        repo = payload["repository"]
        alert_number = alert["number"]
        repo_name = repo["name"]

        logger.info(
            f"Processing Dependabot alert event: {action} for alert {alert_number} in {repo_name}"
        )

        config = cast(GithubDependabotAlertConfig, resource_config)
        current_state = DEPENDABOT_ACTION_TO_STATE[action]

        if current_state not in config.selector.states:

            alert = enrich_with_repository(alert, repo_name)

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[alert]
            )

        rest_client = create_github_client()
        exporter = RestDependabotAlertExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleDependabotAlertOptions(repo_name=repo_name, alert_number=alert_number)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
