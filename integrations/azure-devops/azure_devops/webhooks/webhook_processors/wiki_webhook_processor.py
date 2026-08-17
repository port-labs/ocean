from typing import Any, Dict

from loguru import logger
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)

from azure_devops.misc import Kind
from azure_devops.webhooks.events import PushEvents
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)

WIKI_REPO_SUFFIX = ".wiki"


class WikiWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.WIKI]

    async def should_process_event(self, event: WebhookEvent) -> bool:
        event_type = event.payload.get("eventType")
        if event_type != PushEvents.PUSH:
            return False
        repo_name = (
            event.payload.get("resource", {}).get("repository", {}).get("name", "")
        )
        return repo_name.endswith(WIKI_REPO_SUFFIX)

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        repository = payload["resource"].get("repository", {})
        return (
            repository.get("id") is not None
            and repository.get("name", "").endswith(WIKI_REPO_SUFFIX)
            and repository.get("project", {}).get("id") is not None
        )

    async def _handle_webhook_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        resource = payload["resource"]
        repository = resource["repository"]
        repo_id = repository["id"]
        project_id = repository["project"]["id"]

        client = self._get_client_for_webhook(payload)

        wiki = await client.get_wiki(project_id, repo_id)
        if not wiki:
            logger.warning(
                f"No wiki found for repository {repository['name']} "
                f"(project {project_id})"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        project: Dict[str, Any] = repository["project"]
        wiki["__project"] = project

        pages: list[Dict[str, Any]] = []
        async for page_batch in client.get_wiki_pages_batch(
            project_id, wiki["id"], wiki["name"]
        ):
            for page in page_batch:
                page["__wiki"] = wiki
                page["__project"] = project
            pages.extend(page_batch)

        logger.info(
            f"Wiki push: fetched {len(pages)} pages from wiki {wiki['name']} "
            f"in project {project_id}"
        )

        return WebhookEventRawResults(
            updated_raw_results=pages, deleted_raw_results=[]
        )
