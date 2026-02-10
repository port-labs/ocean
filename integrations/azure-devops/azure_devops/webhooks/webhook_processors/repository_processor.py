from typing import Any, Optional, Dict, cast

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.misc import Kind
from azure_devops.webhooks.events import RepositoryEvents
from azure_devops.webhooks.webhook_processors.base_processor import (
    AzureDevOpsBaseWebhookProcessor,
)
from integration import AzureDevopsRepositoryResourceConfig
from loguru import logger

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class RepositoryWebhookProcessor(AzureDevOpsBaseWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kind.REPOSITORY]

    async def validate_payload(self, payload: EventPayload) -> bool:
        if not await super().validate_payload(payload):
            return False

        return payload["resource"].get("repository", {}).get("id") is not None

    async def should_process_event(self, event: WebhookEvent) -> bool:
        try:
            event_type = event.payload["eventType"]
            return bool(RepositoryEvents(event_type))
        except ValueError:
            return False

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repository_id = payload["resource"]["repository"]["id"]
        client = AzureDevopsClient.create_from_ocean_config()
        repository = await self._get_repository_data(client, repository_id)
        if not repository:
            return WebhookEventRawResults(
                updated_raw_results=[],
                deleted_raw_results=[],
            )

        selector = cast(AzureDevopsRepositoryResourceConfig, resource_config).selector
        attached_files = selector.attached_files or []
        if attached_files:
            repository = await self._enrich_with_attached_files(
                client, repository, attached_files
            )

        return WebhookEventRawResults(
            updated_raw_results=[repository],
            deleted_raw_results=[],
        )

    @staticmethod
    async def _get_repository_data(
        client: AzureDevopsClient, repository_id: str
    ) -> Optional[Dict[str, Any]]:
        repository = await client.get_repository(repository_id)
        if not repository:
            logger.warning(f"Repository with ID {repository_id} not found")
            return None

        return {"kind": Kind.REPOSITORY, **repository}

    @staticmethod
    async def _enrich_with_attached_files(
        client: AzureDevopsClient,
        repo_data: Dict[str, Any],
        file_paths: list[str],
    ) -> Dict[str, Any]:
        """Enrich a repository dict with __attachedFiles."""
        repo_id = repo_data.get("id", "")
        default_branch_ref = repo_data.get("defaultBranch", "refs/heads/main")
        branch_name = default_branch_ref.replace("refs/heads/", "")
        attached: Dict[str, Any] = {}

        for file_path in file_paths:
            try:
                content_bytes = await client.get_file_by_branch(
                    file_path, repo_id, branch_name
                )
                attached[file_path] = (
                    content_bytes.decode("utf-8") if content_bytes else None
                )
            except Exception as e:
                logger.debug(
                    f"Could not fetch file {file_path} from repo {repo_data.get('name', repo_id)}@{branch_name}: {e}"
                )
                attached[file_path] = None

        repo_data["__attachedFiles"] = attached
        return repo_data
