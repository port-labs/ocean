from typing import Any, NamedTuple, Optional, cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import (
    get_matching_files,
    group_files_by_status,
)
from github.core.exporters.mcp_exporter.utils import (
    build_mcp_raw_item,
    iter_mcp_servers,
)
from github.core.options import FileContentOptions
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from integration import GithubFilePattern, GithubMcpResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class McpFileFetch(NamedTuple):
    """Result of trying to read and JSON-parse an mcp.json/.mcp.json at a ref.

    ``ok=False`` covers a missing file, a silently-swallowed 401/403/404 (GitHub's
    default client behavior returns an empty response for those — indistinguishable
    from "not found"), an oversized/non-file response, and unparsable JSON. Callers
    must not treat ``ok=False`` as "the file has zero servers" — only a confirmed
    fetch (``ok=True``) can be trusted for that.
    """

    ok: bool
    servers: dict[str, dict[str, Any]]
    blob_sha: Optional[str]


class McpWebhookProcessor(FileWebhookProcessor):
    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.MCP]

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

        selector = cast(GithubMcpResourceConfig, resource_config).selector

        matching_patterns = self._get_matching_patterns(
            [
                GithubFilePattern(
                    path=pattern.path,
                    organization=pattern.organization,
                    repos=pattern.repos,
                    excludeArchived=pattern.exclude_archived,
                )
                for pattern in selector.paths
            ],
            organization,
            repository,
            current_branch,
            default_branch,
        )
        if not matching_patterns:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = await create_github_client_for_org(organization)
        exporter = RestFileExporter(rest_client)
        diff_data = await exporter.fetch_commit_diff(
            organization, repo_name, before_sha, after_sha
        )
        mcp_changes = get_matching_files(
            diff_data.get("files") or [], matching_patterns
        )
        if not mcp_changes:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        deleted_files, updated_files = group_files_by_status(mcp_changes)

        updated_raw_results: list[dict[str, Any]] = []
        deleted_raw_results: list[dict[str, Any]] = []

        for file_info in updated_files:
            path = file_info["filename"]
            new_fetch = await self._fetch_mcp_servers(
                exporter, organization, repo_name, path, current_branch, repository
            )
            if not new_fetch.ok:
                logger.warning(
                    f"Skipping mcp reconciliation for {path} in "
                    f"{organization}/{repo_name}: could not confirm its current "
                    "content on this push (missing, forbidden, oversized, or "
                    "unparsable) — it will be reconciled on the next full resync "
                    "instead of being treated as having zero servers"
                )
                continue

            for name, server_config in new_fetch.servers.items():
                updated_raw_results.append(
                    build_mcp_raw_item(
                        file_path=path,
                        server_name=name,
                        server_config=server_config,
                        repository=repository,
                        branch=current_branch,
                        organization=organization,
                        blob_sha=new_fetch.blob_sha,
                    )
                )

            old_fetch = await self._fetch_mcp_servers(
                exporter, organization, repo_name, path, before_sha, repository
            )
            if not old_fetch.ok:
                # We can't confirm what used to be there, so we can't safely tell
                # a real removal apart from a fetch that merely failed. Skipping
                # only means a removed server lags until the next full resync —
                # it never causes an incorrect delete.
                continue

            for name in old_fetch.servers.keys() - new_fetch.servers.keys():
                deleted_raw_results.append(
                    build_mcp_raw_item(
                        file_path=path,
                        server_name=name,
                        server_config={},
                        repository=repository,
                        branch=current_branch,
                        organization=organization,
                        blob_sha=old_fetch.blob_sha,
                    )
                )

        for file_info in deleted_files:
            path = file_info["filename"]
            old_fetch = await self._fetch_mcp_servers(
                exporter, organization, repo_name, path, before_sha, repository
            )
            if not old_fetch.ok:
                logger.warning(
                    f"Skipping delete reconciliation for removed file {path} in "
                    f"{organization}/{repo_name}: could not confirm its prior "
                    "content — it will be reconciled on the next full resync"
                )
                continue

            for name in old_fetch.servers:
                deleted_raw_results.append(
                    build_mcp_raw_item(
                        file_path=path,
                        server_name=name,
                        server_config={},
                        repository=repository,
                        branch=current_branch,
                        organization=organization,
                        blob_sha=old_fetch.blob_sha,
                    )
                )

        logger.info(
            f"MCP webhook processed {len(updated_raw_results)} updates and "
            f"{len(deleted_raw_results)} deletes"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )

    async def _fetch_mcp_servers(
        self,
        exporter: RestFileExporter,
        organization: str,
        repo_name: str,
        file_path: str,
        branch: Optional[str],
        repository: dict[str, Any],
    ) -> McpFileFetch:
        """Fetch and JSON-parse an mcp.json/.mcp.json file at a given ref
        (branch name or commit SHA). See `McpFileFetch` for what `ok` means.
        """
        file_data = await exporter.get_resource(
            FileContentOptions(
                organization=organization,
                repo_name=repo_name,
                file_path=file_path,
                branch=branch,
            )
        )
        if not file_data:
            return McpFileFetch(ok=False, servers={}, blob_sha=None)

        content = file_data.get("content")
        if not isinstance(content, str):
            return McpFileFetch(ok=False, servers={}, blob_sha=file_data.get("sha"))

        file_obj = await exporter.file_processor.process_file(
            organization=organization,
            content=content,
            repository=repository,
            file_path=file_path,
            skip_parsing=False,
            branch=branch or "",
            metadata=file_data,
        )
        parsed = file_obj.get("content")
        if not isinstance(parsed, dict):
            return McpFileFetch(ok=False, servers={}, blob_sha=file_data.get("sha"))

        return McpFileFetch(
            ok=True,
            servers=dict(iter_mcp_servers(parsed)),
            blob_sha=file_data.get("sha"),
        )
