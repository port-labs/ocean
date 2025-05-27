from loguru import logger
from github.webhook.events import CODE_SCANNING_ALERT_DELETE_EVENTS, CODE_SCANNING_ALERT_UPSERT_EVENTS
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
from github.core.exporters.code_scanning_alert_exporter import RestCodeScanningAlertExporter
from github.core.options import SingleCodeScanningAlertOptions

class CodeScanningAlertWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "alert", "repository"} <= payload.keys():
            return False

        if payload["action"] not in (
            CODE_SCANNING_ALERT_UPSERT_EVENTS + CODE_SCANNING_ALERT_DELETE_EVENTS
        ):
            return False

        return bool(payload["alert"].get("number") and payload["repository"].get("name")) 

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        print(event.payload)
        print(event.headers.get("x-github-event"))
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

        logger.info(f"Processing code scanning alert event: {action} for alert {alert_number} in {repo_name}")

        if action in CODE_SCANNING_ALERT_DELETE_EVENTS:
            alert["repo"] = repo_name
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[alert]
            )

        rest_client = create_github_client()
        exporter = RestCodeScanningAlertExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleCodeScanningAlertOptions(repo_name=repo_name, alert_number=alert_number)
        )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

