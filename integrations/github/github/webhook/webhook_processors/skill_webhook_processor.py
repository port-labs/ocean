import asyncio
from pathlib import PurePosixPath
from typing import Any, Optional, cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.file_exporter.utils import (
    filter_github_tree_entries_by_pattern,
    get_matching_files,
    group_files_by_status,
)
from github.core.exporters.skill_exporter import SkillExporter
from github.core.exporters.skill_exporter.references import (
    glob_base_dir,
    skill_dir_prefix,
)
from github.core.exporters.skill_exporter.utils import (
    SKILL_MD_FILENAME,
    build_skill_raw_item,
)
from github.core.options import FileContentOptions
from github.helpers.utils import ObjectKind
from github.webhook.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from integration import GithubFilePattern, GithubSkillResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class SkillWebhookProcessor(FileWebhookProcessor):
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
        path_globs = [pattern.path for pattern in selector.paths]

        matching_patterns = self._get_matching_patterns(
            [
                GithubFilePattern(
                    path=pattern.path,
                    organization=pattern.organization,
                    repos=pattern.repos,
                    skipParsing=True,
                    validationCheck=False,
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
        exporter = SkillExporter(
            rest_client, include_references=selector.include_references
        )
        diff_data = await exporter.fetch_commit_diff(
            organization, repo_name, before_sha, after_sha
        )
        diff_files = diff_data.get("files") or []

        deleted_files, updated_files = group_files_by_status(
            get_matching_files(diff_files, matching_patterns)
        )
        deleted_paths = {file_info["filename"] for file_info in deleted_files}
        updated_paths = {file_info["filename"] for file_info in updated_files}
        if selector.include_references:
            updated_paths |= await self._skills_with_changed_references(
                exporter,
                organization,
                repo_name,
                after_sha,
                diff_files,
                matching_patterns,
            )
        skill_md_paths = sorted(updated_paths - deleted_paths)

        updated_items = await asyncio.gather(
            *(
                self._build_updated_skill(
                    exporter,
                    organization,
                    repository,
                    current_branch,
                    after_sha,
                    skill_md_path,
                    path_globs,
                )
                for skill_md_path in skill_md_paths
            )
        )
        updated_raw_results = [item for item in updated_items if item is not None]

        def deleted_skill(
            skill_md_path: str, blob_sha: Optional[str] = None
        ) -> dict[str, Any]:
            return build_skill_raw_item(
                skill_md_path=skill_md_path,
                content="",
                repository=repository,
                branch=current_branch,
                organization=organization,
                path_globs=path_globs,
                blob_sha=blob_sha,
            )

        # A skill that can no longer be built (unreadable, or over the references
        # size limit) is removed, as a resync would drop it.
        deleted_raw_results = [
            deleted_skill(file_info["filename"], file_info.get("sha"))
            for file_info in deleted_files
        ] + [
            deleted_skill(skill_md_path)
            for skill_md_path, item in zip(skill_md_paths, updated_items)
            if item is None
        ]

        logger.info(
            f"Skill webhook processed {len(updated_raw_results)} updates and "
            f"{len(deleted_raw_results)} deletes"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )

    async def _skills_with_changed_references(
        self,
        exporter: SkillExporter,
        organization: str,
        repo_name: str,
        commit_sha: str,
        diff_files: list[dict[str, Any]],
        patterns: list[GithubFilePattern],
    ) -> set[str]:
        """SKILL.md paths whose folder contains a changed file.

        Adding or removing a nested SKILL.md moves its folder out of or into the
        parent's bundle, so it counts; editing a SKILL.md only affects that skill.
        The tree is read at the pushed commit, not the branch: the tree cache
        lives across webhook events, so a branch tree may predate this push.
        """
        skill_roots = tuple(glob_base_dir(pattern.path) for pattern in patterns)
        changed_paths: set[str] = set()
        for file_info in diff_files:
            is_skill_md_edit = (
                PurePosixPath(file_info["filename"]).name == SKILL_MD_FILENAME
                and file_info.get("status") == "modified"
            )
            if is_skill_md_edit:
                continue
            for path in (file_info["filename"], file_info.get("previous_filename")):
                if path and path.startswith(skill_roots):
                    changed_paths.add(path)
        if not changed_paths:
            return set()

        tree, _ = await exporter.get_tree_recursive(organization, repo_name, commit_sha)
        skill_md_paths = {
            entry["path"]
            for pattern in patterns
            for entry in filter_github_tree_entries_by_pattern(tree, pattern.path)
        }
        return {
            skill_md_path
            for skill_md_path in skill_md_paths
            if any(
                path.startswith(skill_dir_prefix(skill_md_path))
                for path in changed_paths
            )
        }

    async def _build_updated_skill(
        self,
        exporter: SkillExporter,
        organization: str,
        repository: dict[str, Any],
        branch: str,
        commit_sha: str,
        skill_md_path: str,
        path_globs: list[str],
    ) -> Optional[dict[str, Any]]:
        file_data = await exporter.get_resource(
            FileContentOptions(
                organization=organization,
                repo_name=repository["name"],
                file_path=skill_md_path,
                branch=branch,
            )
        )
        if not file_data or not isinstance(file_data.get("content"), str):
            return None
        return await exporter.build_skill_item(
            skill_md_path=skill_md_path,
            content=file_data["content"],
            repository=repository,
            branch=branch,
            organization=organization,
            path_globs=path_globs,
            blob_sha=file_data.get("sha"),
            ref=commit_sha,
        )
