from typing import cast
from loguru import logger
from github.core.exporters.folder_exporter import RestFolderExporter
from github.helpers.utils import ObjectKind
from github.clients.client_factory import create_github_client
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from github.core.options import ListFolderOptions
from integration import GithubFolderResourceConfig


class FolderWebhookProcessor(_GithubAbstractWebhookProcessor):
    async def _should_process_event(self, event: WebhookEvent) -> bool:
        return event.headers.get("x-github-event") == "push"

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.FOLDER]

    async def validate_payload(self, payload: EventPayload) -> bool:
        return "ref" in payload and "repository" in payload

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        repository = payload["repository"]
        branch = payload.get("ref", "").replace("refs/heads/", "")
        ref = payload["after"]
        logger.info(
            f"Processing push event for project {repository['name']} on branch {branch} at ref {ref}"
        )

        config = cast(GithubFolderResourceConfig, resource_config)
        selector = config.selector
        folder_selector = selector.folders

        client = create_github_client()
        exporter = RestFolderExporter(client)

        folders = []
        for pattern in folder_selector:
            # Check if this pattern applies to the event's repo and branch
            matched_repo = False
            for repo in pattern.repos:
                if repo.name == repository["name"] and (
                    repo.branch is None or repo.branch == branch
                ):
                    matched_repo = True
                    break
            if not matched_repo:
                continue

            logger.debug(
                f"Fetching folders for path '{pattern.path}' in {repository['name']} on branch {branch}"
            )
            async for folder_batch in exporter.get_paginated_resources(
                ListFolderOptions(repo=repository, path=pattern.path, branch=branch)
            ):
                folders.extend(folder_batch)

        if not folders:
            logger.info(
                f"No folders found matching patterns for {repository['name']} at ref {ref}"
            )
        else:
            logger.info(
                f"Completed push event processing; updated {len(folders)} folders"
            )

        return WebhookEventRawResults(
            updated_raw_results=folders, deleted_raw_results=[]
        )
