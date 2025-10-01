from loguru import logger
from github.webhook.events import SECRET_SCANNING_ALERT_ACTION_TO_STATE
from github.helpers.utils import ObjectKind, enrich_with_repository
from github.clients.client_factory import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.options import SingleSecretScanningAlertOptions
from github.core.exporters.secret_scanning_alert_exporter import (
    RestSecretScanningAlertExporter,
)
from typing import cast
from integration import GithubSecretScanningAlertConfig
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)


class SecretScanningAlertWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "alert" in payload and "number" in payload["alert"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "secret_scanning_alert"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SECRET_SCANNING_ALERT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        alert = payload["alert"]
        repo = payload["repository"]
        alert_number = alert["number"]
        repo_name = repo["name"]

        logger.info(
            f"Processing Secret Scanning alert event: {action} for alert {alert_number} in {repo_name}"
        )

        config = cast(GithubSecretScanningAlertConfig, resource_config)
        possible_states = SECRET_SCANNING_ALERT_ACTION_TO_STATE.get(action, [])

        if not possible_states:
            logger.info(
                f"The action {action} is not allowed for secret scanning alert {alert_number} in {repo_name}. Skipping resource."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if (
            config.selector.state != "all"
            and config.selector.state not in possible_states
        ):
            logger.info(
                f"The action {action} is not allowed for secret scanning alert {alert_number} in {repo_name}. Deleting resource."
            )

            alert = enrich_with_repository(alert, repo_name)

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[alert]
            )

        logger.info(
            f"The action {action} is allowed for secret scanning alert {alert_number} in {repo_name}. Updating resource."
        )

        rest_client = create_github_client(payload["organization"]["login"])
        exporter = RestSecretScanningAlertExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleSecretScanningAlertOptions(
                repo_name=repo_name,
                alert_number=alert_number,
                hide_secret=config.selector.hide_secret,
            )
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
