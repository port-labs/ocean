from typing import Any, cast
from loguru import logger
from github.webhook.events import REPOSITORY_DELETE_EVENTS, REPOSITORY_UPSERT_EVENTS
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from integration import GithubRepositoryConfig
from github.core.options import (
    SingleRepositoryOptions,
    FileContentOptions,
)
from github.core.exporters.repository_exporter import (
    RestRepositoryExporter,
)
from github.core.exporters.file_exporter.core import RestFileExporter


class RepositoryWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        action = payload.get("action")
        if not action:
            return False

        valid_actions = REPOSITORY_UPSERT_EVENTS + REPOSITORY_DELETE_EVENTS
        return action in valid_actions

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "repository"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.REPOSITORY]

    @staticmethod
    async def _enrich_with_included_files(
        rest_client: Any,
        repo_data: dict[str, Any],
        file_paths: list[str],
    ) -> dict[str, Any]:
        """Enrich a repository dict with __includedFiles."""
        repo_name = repo_data["name"]
        organization = repo_data["owner"]["login"]
        default_branch = repo_data.get("default_branch")
        included: dict[str, Any] = {}
        file_exporter = RestFileExporter(rest_client)

        for file_path in file_paths:
            try:
                response = await file_exporter.get_resource(
                    FileContentOptions(
                        organization=organization,
                        repo_name=repo_name,
                        file_path=file_path,
                        branch=default_branch,
                    )
                )
                included[file_path] = response.get("content") if response else None
            except Exception as e:
                logger.debug(
                    f"Could not fetch file {file_path} from {organization}/{repo_name}: {e}"
                )
                included[file_path] = None

        repo_data["__includedFiles"] = included
        return repo_data

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        action = payload["action"]
        repo = payload["repository"]
        name = repo["name"]
        organization = self.get_webhook_payload_organization(payload)["login"]
        resource_config = cast(GithubRepositoryConfig, resource_config)

        logger.info(
            f"Processing repository event: {action} for {name} from {organization}"
        )

        if not await self.should_process_repo_search(payload, resource_config):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if action in REPOSITORY_DELETE_EVENTS:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[repo]
            )

        rest_client = create_github_client()
        exporter = RestRepositoryExporter(rest_client)

        options = SingleRepositoryOptions(
            organization=organization,
            name=name,
            included_relationships=cast(list[str], resource_config.selector.include),
        )

        data_to_upsert = await exporter.get_resource(options)
        if not data_to_upsert:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        included_files = resource_config.selector.included_files or []
        if included_files:
            data_to_upsert = await self._enrich_with_included_files(
                rest_client, data_to_upsert, included_files
            )

        return WebhookEventRawResults(
            updated_raw_results=[data_to_upsert], deleted_raw_results=[]
        )
