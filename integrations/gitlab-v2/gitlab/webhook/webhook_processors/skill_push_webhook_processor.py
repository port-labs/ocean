from pathlib import Path
from typing import cast

from loguru import logger

from gitlab.helpers.skill_plugin import (
    enrich_file_to_skill,
    infer_skill_root,
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
        branch = payload.get("ref", "").removeprefix("refs/heads/")
        repo_path = project["path_with_namespace"]
        default_branch = project.get("default_branch")
        if default_branch and branch != default_branch:
            logger.info(
                f"Skipping skill push for {repo_path} on non-default branch {branch}"
            )
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        config = cast(GitLabSkillResourceConfig, resource_config)
        selector = config.selector
        path_entries = selector.paths
        path_globs = [entry.path for entry in path_entries]

        applicable_globs = [
            entry.path
            for entry in path_entries
            if not entry.repos or repo_path in entry.repos
        ]
        if not applicable_globs:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        changed_files, removed_files = await resolve_push_path_changes(
            self._gitlab_webhook_client, repo_path, payload
        )

        matching_changed = sorted(
            p for p in changed_files if matches_skill_path(p, applicable_globs)
        )
        matching_removed = sorted(
            p for p in removed_files if matches_skill_path(p, applicable_globs)
        )

        if not matching_changed and not matching_removed:
            return WebhookEventRawResults(
                updated_raw_results=[], deleted_raw_results=[]
            )

        updated_results = []
        if matching_changed:
            file_batch = [
                {
                    "project_id": str(project_id),
                    "path": file_path,
                    "ref": payload["after"],
                }
                for file_path in matching_changed
            ]
            processed = await self._gitlab_webhook_client._process_file_batch(
                file_batch,
                context=f"project:{project_id}",
                skip_parsing=True,
            )
            enriched = await self._gitlab_webhook_client._enrich_files_with_repos(
                processed
            )
            for entity in enriched:
                skill_item = enrich_file_to_skill(entity, path_globs=path_globs)
                if skill_item:
                    updated_results.append(skill_item)

        deleted_results = []
        for path in matching_removed:
            path_obj = Path(path)
            skill_dir = str(path_obj.parent).replace("\\", "/")
            deleted_results.append(
                {
                    "skill": {
                        "name": path_obj.parent.name,
                        "description": "",
                        "instructions": None,
                        "frontmatter": {},
                        "path": skill_dir,
                        "skillMdPath": path,
                        "root": infer_skill_root(path, path_globs),
                    },
                    "repo": project,
                    "__branch": branch,
                }
            )

        logger.info(
            f"Skill push webhook for {repo_path}: "
            f"{len(updated_results)} updates, {len(deleted_results)} deletes"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_results,
            deleted_raw_results=deleted_results,
        )
