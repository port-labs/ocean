from loguru import logger
from github.core.exporters.user_exporter import GraphQLUserExporter
from github.webhook.events import (
    USER_DELETE_EVENTS,
    USER_UPSERT_EVENTS,
)
from github.helpers.utils import GithubClientType, ObjectKind
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
from github.core.options import SingleUserOptions


class UserWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        if not event.payload.get("action"):
            return False

        if event.payload["action"] not in (USER_UPSERT_EVENTS + USER_DELETE_EVENTS):
            return False
        return event.headers.get("x-github-event") == "organization"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.USER]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        membership = payload["membership"]
        user = membership["user"]

        logger.info(f"Processing event: {action}")

        if action in USER_DELETE_EVENTS:
            logger.info(f"User {user['login']} was removed from org")

            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[user]
            )

        client = create_github_client(GithubClientType.GRAPHQL)
        exporter = GraphQLUserExporter(client)

        data_to_upsert = await exporter.get_resource(
            SingleUserOptions(login=user["login"])
        )

        logger.info(f"User {user['login']} was upserted")
        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "membership"} <= payload.keys():
            return False

        return bool(payload["membership"].get("user"))
