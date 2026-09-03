from loguru import logger

from github.webhook.events import (
    ORGANIZATION_DELETE_EVENTS,
    ORGANIZATION_EVENTS,
)
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.organization_exporter import RestOrganizationExporter
from github.core.options import SingleOrganizationOptions
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class OrganizationWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if not event.payload.get("action"):
            return False
        if event.payload["action"] not in ORGANIZATION_EVENTS:
            return False
        return event.headers.get("x-github-event") == "organization"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.ORGANIZATION]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        organization = self.get_webhook_payload_organization(payload)
        org_login = organization["login"]

        logger.info(f"Processing organization event: {action} for {org_login}")

        if action in ORGANIZATION_DELETE_EVENTS:
            logger.info(f"Organization {org_login} was deleted")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[organization]
            )

        rest_client = await create_github_client_for_org(org_login)
        exporter = RestOrganizationExporter(rest_client)

        data_to_upsert = await exporter.get_resource(
            SingleOrganizationOptions(organization=org_login)
        )
        if not data_to_upsert:
            logger.warning(
                f"Failed to fetch organization {org_login} after {action} event"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(f"Organization {org_login} was upserted (action: {action})")
        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "organization"} <= payload.keys():
            return False
        return bool(payload["organization"].get("login"))
