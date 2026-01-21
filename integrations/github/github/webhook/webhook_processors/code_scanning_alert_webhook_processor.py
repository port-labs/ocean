from typing import cast, Any
from loguru import logger
from github.webhook.events import (
    CODE_SCANNING_ALERT_ACTION_TO_STATE,
)
from github.helpers.utils import (
    ObjectKind,
    enrich_with_repository,
    enrich_with_organization,
)
from github.clients.client_factory import create_github_client
from integration import GithubCodeScanningAlertConfig, GithubCodeScanningAlertSelector
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.core.exporters.code_scanning_alert_exporter import (
    RestCodeScanningAlertExporter,
)
from github.core.options import SingleCodeScanningAlertOptions


class CodeScanningAlertWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        return "alert" in payload and "number" in payload["alert"]

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "code_scanning_alert"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.CODE_SCANNING_ALERT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        alert = payload["alert"]
        repo = payload["repository"]
        alert_number = alert["number"]
        repo_name = repo["name"]
        organization = self.get_webhook_payload_organization(payload)["login"]

        logger.info(
            f"Processing code scanning alert event: {action} for alert {alert_number} in {repo_name} from {organization}"
        )

        config = cast(GithubCodeScanningAlertConfig, resource_config)
        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        possible_states = CODE_SCANNING_ALERT_ACTION_TO_STATE.get(action, [])

        if not self._check_alert_filters(config.selector, alert):
            logger.info(
                f"Code scanning alert {repo_name}/{alert_number} filtered out by selector criteria"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not possible_states:
            logger.info(
                f"The action {action} is not allowed for code scanning alert {alert_number} in {repo_name} from {organization}. Skipping resource."
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if config.selector.state not in possible_states:
            logger.info(
                f"The action {action} is not allowed for code scanning alert {alert_number} in {repo_name} from {organization}. Deleting resource."
            )

            alert = enrich_with_organization(
                enrich_with_repository(alert, repo_name), organization
            )

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[alert]
            )

        rest_client = create_github_client()
        exporter = RestCodeScanningAlertExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleCodeScanningAlertOptions(
                organization=organization,
                repo_name=repo_name,
                alert_number=alert_number,
            )
        )
        if not data_to_upsert:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    def _check_alert_filters(
        self, selector: GithubCodeScanningAlertSelector, alert: dict[str, Any]
    ) -> bool:
        """Check if alert matches selector severity filter."""
        alert_severity = alert["rule"]["severity"]
        if selector.severity and alert_severity.lower() != selector.severity.lower():
            return False
        return True
