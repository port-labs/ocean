import os
from typing import Any, Set

from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.webhook.config_change_processor import (
    BaseConfigChangeWebhookProcessor,
)

from github.webhook.webhook_processors.github_abstract_webhook_processor import (
    _GithubAbstractWebhookProcessor,
)
from github.core.exporters.file_exporter.utils import group_files_by_status
from github.helpers.port_app_config import (
    is_repo_managed_mapping,
    validate_config_file_name,
)
from github.core.exporters.file_exporter.core import RestFileExporter
from github.clients.client_factory import create_github_client
from github.helpers.port_app_config import ORG_CONFIG_FILE, ORG_CONFIG_REPO


class PortAppConfigWebhookProcessor(
    BaseConfigChangeWebhookProcessor, _GithubAbstractWebhookProcessor
):
    """
    Webhook processor that reacts to changes in the global `port-app-config.yml`
    configuration file for the GitHub Ocean integration.

    Behavior:
    - Listens to GitHub `push` events.
    - Filters events to the `.github-private` repository on its default branch.
    - If any commit in the push touches `port-app-config.yml` and the integration
      mapping is managed via `repoManagedMapping: true`, triggers a full resync.
    """

    async def validate_payload(self, payload: EventPayload) -> bool:

        required_keys = {"ref", "before", "after", "commits", "repository"}
        return (
            await super().validate_payload(payload)
            and not (required_keys - payload.keys())
            and "default_branch" in payload.get("repository", {})
            and "name" in payload.get("repository", {})
        )

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        is_push_event = event.headers.get("x-github-event") == "push"
        is_github_private_repo = (
            event.payload.get("repository", {}).get("name") == ORG_CONFIG_REPO
        )
        has_branch_name = event.payload.get("ref", "").startswith("refs/heads/")

        return is_push_event and is_github_private_repo and has_branch_name

    async def get_matching_kinds(self, _: WebhookEvent) -> list[str]:
        # This processor only triggers a resync and does not emit raw results
        return []

    async def handle_event(
        self, payload: EventPayload, _: ResourceConfig
    ) -> WebhookEventRawResults:
        organization = self.get_webhook_payload_organization(payload)["login"]
        repository = payload["repository"]
        repo_name = repository["name"]
        default_branch = repository["default_branch"]
        current_branch = payload["ref"].split("/")[-1]
        before_sha = payload["before"]
        after_sha = payload["after"]

        if repo_name != ORG_CONFIG_REPO:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        if not current_branch or current_branch != default_branch:
            logger.info(
                "Skipping global Port app config change because push is not on "
                "the default branch",
                extra={
                    "organization": organization,
                    "repository": repo_name,
                    "default_branch": default_branch,
                    "current_branch": current_branch,
                },
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)

        diff_data = await exporter.fetch_commit_diff(
            organization, repo_name, before_sha, after_sha
        )
        files_to_process = diff_data.get("files", [])
        deleted_files, updated_files = group_files_by_status(files_to_process)

        changed_paths: Set[str] = {f["filename"] for f in deleted_files + updated_files}

        if not any(
            os.path.basename(path).startswith(ORG_CONFIG_FILE) for path in changed_paths
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        integration: dict[str, Any] = await ocean.port_client.get_current_integration(
            should_log=False, should_raise=False
        )

        if not is_repo_managed_mapping(integration):
            logger.info(
                "Detected change to global Port app config in GitHub, but "
                "mapping is not managed by the repository; skipping resync",
                extra={
                    "organization": organization,
                    "repository": repo_name,
                },
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config_file_name = validate_config_file_name(
            integration.get("config", {}).get("configFileName")
        )
        if config_file_name not in changed_paths:
            logger.info(
                "Detected change to global Port app config in GitHub, but "
                "config file name is not in the changed paths; skipping resync",
                extra={
                    "organization": organization,
                    "repository": repo_name,
                    "config_file_name": config_file_name,
                },
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info(
            "Detected change to global Port app config in GitHub; triggering full "
            "resync for GitHub Ocean integration",
            extra={"organization": organization, "repository": repo_name},
        )

        await self.trigger_resync()

        return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])
