import json
from typing import Any, cast

from loguru import logger

from gitlab.helpers.skill_plugin import (
    DEFAULT_PLUGIN_PROVIDERS,
    all_manifest_paths,
    detect_directory_providers,
    normalize_plugin,
    path_touches_plugin,
)
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from integration import GitLabPluginResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class PluginPushWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.PLUGIN]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        project_id = payload["project"]["id"]
        branch = payload.get("ref", "").replace("refs/heads/", "")
        repo_path = payload["project"]["path_with_namespace"]
        project = payload["project"]

        config = cast(GitLabPluginResourceConfig, resource_config)
        selector = config.selector
        providers = selector.providers or list(DEFAULT_PLUGIN_PROVIDERS)
        repos = selector.repos
        manifest_paths = set(all_manifest_paths(providers))

        if repos and repo_path not in repos:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        changed_files: set[str] = set()
        removed_files: set[str] = set()
        for commit in payload.get("commits", []):
            changed_files.update(commit.get("added", []))
            changed_files.update(commit.get("modified", []))
            removed_files.update(commit.get("removed", []))

        all_touched = changed_files | removed_files
        if not any(path_touches_plugin(path, providers) for path in all_touched):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        # Re-fetch all known manifests for this project to rebuild plugin
        file_batch = [
            {
                "project_id": str(project_id),
                "path": path,
                "ref": payload.get("after") or branch,
            }
            for path in sorted(manifest_paths)
        ]
        processed = await self._gitlab_webhook_client._process_file_batch(
            file_batch,
            context=f"project:{project_id}",
            skip_parsing=False,
        )

        manifests: dict[str, Any] = {}
        for file_data in processed:
            path = file_data.get("path") or ""
            if path not in manifest_paths:
                continue
            content = file_data.get("content")
            if isinstance(content, dict):
                manifests[path] = content
            elif isinstance(content, str):
                try:
                    manifests[path] = json.loads(content)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid plugin manifest JSON at {path}")

        # Directory-only providers: infer from non-removed touched plugin paths.
        # Webhook can't cheaply list the full tree, so use live push paths.
        live_paths = {
            p
            for p in (changed_files - removed_files)
            if path_touches_plugin(p, providers)
        }
        directory_supports = detect_directory_providers(live_paths, providers)

        plugin = normalize_plugin(
            repository=project,
            manifests=manifests,
            providers=providers,
            directory_supports=directory_supports,
        )
        if plugin:
            return WebhookEventRawResults(
                updated_raw_results=[
                    {
                        "plugin": plugin,
                        "repository": project,
                        "branch": branch,
                    }
                ],
                deleted_raw_results=[],
            )

        return WebhookEventRawResults(
            updated_raw_results=[],
            deleted_raw_results=[
                {
                    "plugin": {
                        "name": project.get("path") or project.get("name"),
                        "displayName": project.get("name"),
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
                    "repository": project,
                    "branch": branch,
                }
            ],
        )
