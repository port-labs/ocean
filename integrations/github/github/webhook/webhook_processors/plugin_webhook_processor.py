from typing import cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter.core import PluginExporter
from github.core.exporters.plugin_exporter.utils import (
    build_plugin_raw_item,
    empty_plugin,
    find_plugin_roots,
)
from github.core.options import PluginRepositoryOptions
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from integration import GithubPluginResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import RAW_ITEM
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

        # Feature-branch edits do not update the catalog. This keeps the file
        # kind rule: only the configured branch, or the default branch when
        # repos[].branch is unset, is processed.
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
        # Only marker files matter; other files under a plugin (SKILL.md) do not.
        changed_paths = [
            path
            for file_info in diff_data.get("files") or []
            for path in (file_info.get("filename"), file_info.get("previous_filename"))
            if path
        ]
        changed_roots = find_plugin_roots(changed_paths, providers, selector.max_depth)
        if not changed_roots:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        exporter = PluginExporter(rest_client, providers, selector.max_depth)
        options = PluginRepositoryOptions(
            organization=organization, repository=repository, branch=current_branch
        )
        roots, truncated = await exporter.get_plugin_roots(options)
        if truncated:
            logger.warning("Skipping plugin webhook: GitHub tree response was truncated")
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated_raw_results: list[RAW_ITEM] = []
        deleted_raw_results: list[RAW_ITEM] = []
        for root in sorted(changed_roots):
            item = (
                await exporter.build_plugin_item(options, root, roots[root])
                if root in roots
                else None
            )
            if item:
                updated_raw_results.append(item)
            elif truncated:
                logger.warning(f"Skipping delete of plugin {root!r}: tree truncated")
            else:
                deleted_raw_results.append(
                    build_plugin_raw_item(
                        plugin=empty_plugin(
                            name=root.split("/")[-1] or repo_name, path=root
                        ),
                        repository=repository,
                        branch=current_branch,
                        organization=organization,
                    )
                )

        logger.info(
            f"Plugin webhook processed {len(updated_raw_results)} updates and "
            f"{len(deleted_raw_results)} deletes for {organization}/{repo_name}"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
