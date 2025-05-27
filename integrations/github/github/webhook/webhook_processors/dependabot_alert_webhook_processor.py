from loguru import logger
from github.webhook.events import DEPENDABOT_ALERT_EVENTS, DEPENDABOT_ACTION_TO_STATE
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleDependabotAlertOptions
from github.core.exporters.dependabot_alert_exporter import RestDependabotAlertExporter
from typing import Dict, Set, cast
from integration import GithubDependabotAlertConfig


class DependabotAlertWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "alert", "repository"} <= payload.keys():
            return False

        if payload["action"] not in DEPENDABOT_ALERT_EVENTS:
            return False

        return bool(payload["alert"].get("number") and payload["repository"].get("name")) 

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

        logger.info(f"Processing Dependabot alert event: {action} for alert {alert_number} in {repo_name}")

        config = cast(GithubDependabotAlertConfig, resource_config)
        current_state = DEPENDABOT_ACTION_TO_STATE[action]

        if current_state not in config.selector.state:
            alert["repo"] = repo_name
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[alert]
            )

        rest_client = create_github_client()
        exporter = RestDependabotAlertExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleDependabotAlertOptions(repo_name=repo_name, alert_number=alert_number)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

