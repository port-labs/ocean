from typing import cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.core import PluginExporter
from github.core.exporters.plugin_exporter.utils import (
    build_plugin_raw_item,
    empty_plugin,
    path_touches_plugin,
)
from github.core.options import PluginRepositoryOptions
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from integration import GithubPluginResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class PluginWebhookProcessor(FileWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PLUGIN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        organization = self.get_webhook_payload_organization(payload)["login"]
        repository = payload["repository"]
        before_sha = payload["before"]
        after_sha = payload["after"]
        repo_name = repository["name"]
        default_branch = repository["default_branch"]
        current_branch = payload["ref"].removeprefix("refs/heads/")

        selector = cast(GithubPluginResourceConfig, resource_config).selector
        providers = selector.providers

        if not any(
            (
                path.organization is None
                or path.organization.casefold() == organization.casefold()
            )
            and not self._should_skip_archived_repository(path, repository)
            and self._is_pattern_applicable_to_branch(
                path, repo_name, current_branch, default_branch
            )
            for path in selector.paths
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = await create_github_client_for_org(organization)
        diff_data = await RestFileExporter(rest_client).fetch_commit_diff(
            organization, repo_name, before_sha, after_sha
        )
        changed = diff_data.get("files") or []

        if not any(
            path_touches_plugin(file.get("filename", ""), providers) for file in changed
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        exporter = PluginExporter(rest_client, providers)
        plugin_item = await exporter.get_resource(
            PluginRepositoryOptions(
                organization=organization,
                repository=repository,
                branch=current_branch,
            )
        )

        if plugin_item:
            return WebhookEventRawResults(
                updated_raw_results=[plugin_item],
                deleted_raw_results=[],
            )

        if await exporter.is_tree_truncated(organization, repo_name, current_branch):
            logger.warning("Skipping plugin delete: GitHub tree response was truncated")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        logger.info("Plugin manifests removed; emitting delete")
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[
                build_plugin_raw_item(
                    plugin=empty_plugin(name=repo_name),
                    repository=repository,
                    branch=current_branch,
                    organization=organization,
                )
            ],
        )
