from pathlib import PurePosixPath
from typing import Any, cast

from loguru import logger

from gitlab.clients.gitlab_client import _literal_tree_prefix, _minimize_tree_roots
from gitlab.helpers.skill_folder import attach_skill_folder_files, skill_dir_prefix
from gitlab.helpers.skill_plugin import (
    build_skill_delete_stub,
    enrich_file_to_skill,
    matches_skill_path,
)
from gitlab.helpers.utils import ObjectKind
from gitlab.webhook.webhook_processors._gitlab_abstract_webhook_processor import (
    _GitlabAbstractWebhookProcessor,
)
from gitlab.webhook.webhook_processors.push_constants import DELETED_COMMIT_SHA
from gitlab.webhook.webhook_processors.push_path_changes import (
    resolve_push_path_changes,
)
from integration import GitLabSkillResourceConfig
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class SkillPushWebhookProcessor(_GitlabAbstractWebhookProcessor):
    events = ["push"]
    hooks = ["Push Hook"]

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [ObjectKind.SKILL]

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        if payload.get("after") == DELETED_COMMIT_SHA:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        project = payload["project"]
        project_id = project["id"]
        branch = self._get_branch_name(payload)
        repo_path = project["path_with_namespace"]
        if not self._is_default_branch_push(payload, "skill"):
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(GitLabSkillResourceConfig, resource_config)
        selector = config.selector
        path_entries = selector.paths

        applicable_globs = [
            entry.path
            for entry in path_entries
            if not entry.repos or repo_path in entry.repos
        ]
        if not applicable_globs:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        changed_files, removed_files, modified_files = await resolve_push_path_changes(
            self._gitlab_webhook_client, repo_path, payload
        )

        matching_changed = {
            p for p in changed_files if matches_skill_path(p, applicable_globs)
        }
        matching_removed = {
            p for p in removed_files if matches_skill_path(p, applicable_globs)
        }
        if selector.include_skill_folder:
            skill_md_edits = {
                p for p in modified_files if matches_skill_path(p, applicable_globs)
            }
            matching_changed |= await self._skills_with_changed_folders(
                project,
                payload["after"],
                (changed_files | removed_files) - skill_md_edits,
                applicable_globs,
            )
        skill_md_paths = sorted(matching_changed)

        if not skill_md_paths and not matching_removed:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated_results: list[dict[str, Any]] = []
        unbuildable_paths: list[str] = []
        if skill_md_paths:
            file_batch = [
                {
                    "project_id": str(project_id),
                    "path": file_path,
                    "ref": payload["after"],
                }
                for file_path in skill_md_paths
            ]
            processed = await self._gitlab_webhook_client._process_file_batch(
                file_batch,
                context=f"project:{project_id}",
                skip_parsing=True,
            )
            enriched = await self._gitlab_webhook_client._enrich_files_with_repos(
                processed
            )
            skill_items = [
                (skill_item, entity["file"]["content"])
                for entity in enriched
                if (
                    skill_item := enrich_file_to_skill(
                        entity, path_globs=applicable_globs
                    )
                )
            ]
            if selector.include_skill_folder:
                built = await attach_skill_folder_files(
                    self._gitlab_webhook_client, skill_items, ref=payload["after"]
                )
                # Over the size limit: removed, as a resync would drop it.
                unbuildable_paths = [
                    skill_item["skill"]["skillMdPath"]
                    for (skill_item, _), item in zip(skill_items, built)
                    if item is None
                ]
                updated_results = [item for item in built if item is not None]
            else:
                updated_results = [skill_item for skill_item, _ in skill_items]

        deleted_results = [
            {
                "skill": build_skill_delete_stub(
                    skill_md_path=path, path_globs=applicable_globs
                ),
                "repo": project,
                "__branch": branch,
            }
            for path in sorted(matching_removed) + unbuildable_paths
        ]

        logger.info(
            f"Skill push webhook for {repo_path}: "
            f"{len(updated_results)} updates, {len(deleted_results)} deletes"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_results,
            deleted_raw_results=deleted_results,
        )

    async def _skills_with_changed_folders(
        self,
        project: dict[str, Any],
        commit_sha: str,
        changed_paths: set[str],
        path_globs: list[str],
    ) -> set[str]:
        """SKILL.md paths of the closest skill containing each changed path.

        A file inside a nested skill belongs only to that skill, so outer skills
        are not rebuilt for it. `changed_paths` excludes in-place edits of
        SKILL.md, which only affect that skill. Adding or removing a nested
        SKILL.md moves its folder out of or into the parent's bundle, so the
        parent is its owner.
        """
        skill_roots = _minimize_tree_roots(
            {_literal_tree_prefix(pattern) for pattern in path_globs}
        )
        changed_roots = [
            root
            for root in skill_roots
            if any(not root or path.startswith(f"{root}/") for path in changed_paths)
        ]

        skill_md_paths: set[str] = set()
        for root in changed_roots:
            async for batch in self._gitlab_webhook_client.get_repository_tree(
                project, root, commit_sha, recursive=True
            ):
                skill_md_paths.update(
                    entry["path"]
                    for entry in batch
                    if entry.get("type") == "blob"
                    and matches_skill_path(entry["path"], path_globs)
                )
        skill_md_by_prefix = {skill_dir_prefix(path): path for path in skill_md_paths}
        owners: set[str] = set()
        for path in changed_paths:
            for parent in map(str, PurePosixPath(path).parents):
                owner = skill_md_by_prefix.get("" if parent == "." else f"{parent}/")
                if owner is not None and owner != path:
                    owners.add(owner)
                    break
        return owners
