from typing import Any, cast

from loguru import logger

from github.clients.client_factory import create_github_client_for_org
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import (
    get_matching_files,
    group_files_by_status,
)
from github.core.exporters.skill_exporter.utils import build_skill_raw_item
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
                )
                for pattern in selector.paths
            ],
            organization,
            repo_name,
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
        skill_changes = get_matching_files(
            diff_data.get("files") or [], matching_patterns
        )
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
                    repository=repository,
                    branch=current_branch,
                    organization=organization,
                    path_globs=path_globs,
                )
            )

        deleted_raw_results = [
            build_skill_raw_item(
                skill_md_path=file_info["filename"],
                content="",
                repository=repository,
                branch=current_branch,
                organization=organization,
                path_globs=path_globs,
            )
            for file_info in deleted_files
        ]

        logger.info(
            f"Skill webhook processed {len(updated_raw_results)} updates and "
            f"{len(deleted_raw_results)} deletes"
        )
        return WebhookEventRawResults(
            updated_raw_results=updated_raw_results,
            deleted_raw_results=deleted_raw_results,
        )
