from typing import Any, cast

from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.plugin_exporter import (
    DEFAULT_PLUGIN_PROVIDERS,
    PluginExporter,
    all_manifest_paths,
    path_touches_plugin,
)
from github.helpers.port_app_config import ORG_CONFIG_REPO
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from integration import GithubPluginResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class PluginWebhookProcessor(BaseRepositoryWebhookProcessor):
    async def _validate_payload(self, payload: EventPayload) -> bool:
        required_keys = {"ref", "before", "after", "commits"}
        return not (required_keys - payload.keys()) and "default_branch" in payload.get(
            "repository", {}
        )

    async def _should_process_event(self, event: WebhookEvent) -> bool:
        is_push_event = event.headers.get("x-github-event") == "push"
        is_github_private_repo = (
            event.payload.get("repository", {}).get("name") == ORG_CONFIG_REPO
        )
        has_branch_name = event.payload.get("ref", "").startswith("refs/heads/")
        return is_push_event and not is_github_private_repo and has_branch_name

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
        current_branch = payload["ref"].split("/")[-1]

        selector = cast(GithubPluginResourceConfig, resource_config).selector
        providers = selector.providers or list(DEFAULT_PLUGIN_PROVIDERS)

        if not self._is_applicable_to_repo_branch(
            selector, repo_name, current_branch, default_branch
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = create_github_client()
        file_exporter = RestFileExporter(rest_client)
        diff_data = await file_exporter.fetch_commit_diff(
            organization, repo_name, before_sha, after_sha
        )
        changed = diff_data.get("files") or []
        manifest_paths = set(all_manifest_paths(providers))

        touched = [
            f
            for f in changed
            if path_touches_plugin(f.get("filename", ""), providers)
        ]
        if not touched:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        plugin_exporter = PluginExporter(rest_client)
        plugin_item = await plugin_exporter.build_plugin_for_repo(
            organization=organization,
            repository=repository,
            branch=current_branch,
            manifest_paths=manifest_paths,
            providers=providers,
        )

        if plugin_item:
            return WebhookEventRawResults(
                updated_raw_results=[plugin_item],
                deleted_raw_results=[],
            )

        logger.info(
            f"Plugin manifests removed for {organization}/{repo_name}; emitting delete"
        )
        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[
                {
                    "plugin": {
                        "name": repo_name,
                        "displayName": repo_name,
                        "description": "",
                        "version": None,
                        "supports": {
                            "claude": False,
                            "cursor": False,
                            "codex": False,
                            "agents": False,
                            "kimi": False,
                            "opencode": False,
                            "pi": False,
                            "antigravity": False,
                        },
                        "claude": {},
                        "cursor": {},
                        "codex": {},
                        "agents": {},
                        "kimi": {},
                        "opencode": {},
                        "pi": {},
                        "antigravity": {},
                    },
                    "repository": repository,
                    "branch": current_branch,
                    "organization": organization,
                }
            ],
        )

    def _is_applicable_to_repo_branch(
        self,
        selector: Any,
        repo_name: str,
        current_branch: str,
        default_branch: str,
    ) -> bool:
        if selector.repos is None:
            return current_branch == default_branch
        for mapping in selector.repos:
            if mapping.name == repo_name and (
                mapping.branch == current_branch
                or (mapping.branch is None and current_branch == default_branch)
            ):
                return True
        return False
