from loguru import logger
from github.webhook.events import DEPLOYMENT_EVENTS
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
from github.core.exporters.exporter_factory import ExporterFactory


class DeploymentWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "deployment_status"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.DEPLOYMENT, ObjectKind.ENVIRONMENT]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        deployment = payload["deployment"]
        environment = payload["environment"]
        deployment_id = str(deployment["id"])
        env_name = environment["name"]
        repo = payload["repository"]["name"]
        resource_config_kind = resource_config.kind

        logger.info(
            f"Processing deployment event: {action} for {resource_config_kind} in {repo}"
        )

        client = create_github_client()
        exporter_factory = ExporterFactory()

        if resource_config_kind == ObjectKind.ENVIRONMENT:
            exporter = exporter_factory.get_exporter(ObjectKind.ENVIRONMENT)(client)
            data_to_upsert = await exporter.get_resource({"repo": repo, "name": env_name})
        else:  # ObjectKind.DEPLOYMENT
            exporter = exporter_factory.get_exporter(ObjectKind.DEPLOYMENT)(client)
            data_to_upsert = await exporter.get_resource({"repo": repo, "id": deployment_id})

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert],
            deleted_raw_results=[]
        )

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not {"action", "deployment", "environment", "repository"} <= payload.keys():
            return False

        if payload["action"] not in DEPLOYMENT_EVENTS:
            return False

        return bool(
            payload["deployment"].get("id") 
            and payload["environment"].get("name") 
            and payload["repository"].get("name")
        ) 