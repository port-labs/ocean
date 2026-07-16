from pathlib import Path
from typing import Any, cast

from loguru import logger

from github.clients.client_factory import create_github_client
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import group_files_by_status
from github.core.exporters.skill_exporter import (
    DEFAULT_SKILL_ROOTS,
    SKILL_MD_FILENAME,
    build_skill_raw_item,
    match_skill_root,
    path_under_roots_or_extra,
)
from github.core.options import FileContentOptions
from github.helpers.port_app_config import ORG_CONFIG_REPO
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.base_repository_webhook_processor import (
    BaseRepositoryWebhookProcessor,
)
from integration import GithubSkillResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class SkillWebhookProcessor(BaseRepositoryWebhookProcessor):
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
        return [ObjectKind.SKILL]

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

        selector = cast(GithubSkillResourceConfig, resource_config).selector
        effective_roots = selector.roots or list(DEFAULT_SKILL_ROOTS)

        if not self._is_applicable_to_repo_branch(
            selector, repo_name, current_branch, default_branch
        ):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)
        diff_data = await exporter.fetch_commit_diff(
            organization, repo_name, before_sha, after_sha
        )
        changed_files = diff_data.get("files") or []

        skill_changes = [
            file_info
            for file_info in changed_files
            if self._is_skill_path(
                file_info.get("filename", ""),
                effective_roots,
                selector.paths,
            )
        ]

        if not skill_changes:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        deleted_files, updated_files = group_files_by_status(skill_changes)

        updated_raw_results: list[dict[str, Any]] = []
        for file_info in updated_files:
            path = file_info["filename"]
            file_data = await exporter.get_resource(
                FileContentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    file_path=path,
                    branch=current_branch,
                )
            )
            if not file_data or not isinstance(file_data.get("content"), str):
                continue
            updated_raw_results.append(
                build_skill_raw_item(
                    skill_md_path=path,
                    content=file_data["content"],
                    content_mode=selector.content,
                    repository=repository,
                    branch=current_branch,
                    organization=organization,
                    roots=effective_roots,
                )
            )

        deleted_raw_results = []
        for file_info in deleted_files:
            filename = file_info["filename"]
            path_obj = Path(filename)
            skill_dir = str(path_obj.parent).replace("\\", "/")
            deleted_raw_results.append(
                {
                    "skill": {
                        "name": path_obj.parent.name,
                        "description": "",
                        "instructions": None,
                        "frontmatter": {},
                        "path": skill_dir,
                        "skillMdPath": filename,
                        "root": match_skill_root(filename, effective_roots)
                        or skill_dir.split("/")[0],
                    },
                    "repository": repository,
                    "branch": current_branch,
                    "organization": organization,
                }
            )

        logger.info(
            f"Skill webhook processed {len(updated_raw_results)} updates and "
            f"{len(deleted_raw_results)} deletes"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )

    def _is_skill_path(
        self,
        path: str,
        roots: list[str],
        extra_paths: list[str],
    ) -> bool:
        if Path(path).name.lower() != SKILL_MD_FILENAME.lower():
            return False
        return path_under_roots_or_extra(path, roots, extra_paths)
