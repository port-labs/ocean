import asyncio
from typing import Any, List, Optional

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.file_exporter.utils import (
    determine_api_client_type_by_file_size,
)
from github.core.exporters.skill_exporter.skill_folder import (
    MAX_SKILL_BUNDLE_SIZE,
    select_skill_folder_files,
    skill_dir_prefix,
)
from github.core.exporters.skill_exporter.utils import (
    SkillFile,
    build_skill_raw_item,
)
from github.core.options import ListFileSearchOptions
from github.helpers.utils import GithubClientType
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class SkillExporter(RestFileExporter):
    """Discovers SKILL.md files and emits normalized skill entities."""

    def __init__(
        self, client: GithubRestClient, include_skill_folder: bool = False
    ) -> None:
        super().__init__(client)
        self.include_skill_folder = include_skill_folder

    async def get_paginated_resources[ExporterOptionsT: List[ListFileSearchOptions]](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        path_globs = list(
            dict.fromkeys(
                file_options["path"]
                for repo_options in options
                for file_options in repo_options["files"]
            )
        )

        async for file_batch in super().get_paginated_resources(options):
            valid_files = []
            for file_obj in file_batch:
                if isinstance(file_obj.get("content"), str):
                    valid_files.append(file_obj)
                else:
                    logger.warning(
                        f"Skipping skill file {file_obj.get('path')} — "
                        "content is not a string"
                    )

            results = await asyncio.gather(
                *(
                    self.build_skill_item(
                        skill_md_path=file_obj["path"],
                        content=file_obj["content"],
                        repository=file_obj["repository"],
                        branch=file_obj["branch"],
                        organization=file_obj["organization"],
                        path_globs=path_globs,
                        blob_sha=file_obj.get("metadata", {}).get("sha"),
                    )
                    for file_obj in valid_files
                )
            )
            skills = [skill for skill in results if skill is not None]
            if skills:
                yield skills

    async def build_skill_item(
        self,
        *,
        skill_md_path: str,
        content: str,
        repository: dict[str, Any],
        branch: str,
        organization: str,
        path_globs: list[str],
        blob_sha: Optional[str] = None,
        ref: Optional[str] = None,
    ) -> Optional[dict[str, Any]]:
        """Build the skill raw item, or None if its skill folder is too large.

        Folder files are read at `ref` (defaults to `branch`). Pass a commit SHA
        when the branch tree may already be cached from an earlier event.
        """
        files = None
        if self.include_skill_folder:
            files = await self.fetch_skill_folder_files(
                organization=organization,
                repo_name=repository["name"],
                ref=ref or branch,
                skill_md_path=skill_md_path,
                skill_md_size=len(content.encode("utf-8")),
            )
            if files is None:
                return None

        return build_skill_raw_item(
            skill_md_path=skill_md_path,
            content=content,
            repository=repository,
            branch=branch,
            organization=organization,
            path_globs=path_globs,
            blob_sha=blob_sha,
            files=files,
        )

    async def fetch_skill_folder_files(
        self,
        *,
        organization: str,
        repo_name: str,
        ref: str,
        skill_md_path: str,
        skill_md_size: int,
    ) -> Optional[list[SkillFile]]:
        """Fetch the text files in the skill folder at `ref` (branch or commit
        SHA), sorted by relative path.

        Returns None when SKILL.md plus its folder files exceed the bundle limit.
        """
        prefix = skill_dir_prefix(skill_md_path)
        tree, truncated = await self.get_tree_recursive(organization, repo_name, ref)
        if truncated and prefix:
            tree = await self._get_skill_folder_tree(
                organization, repo_name, ref, prefix
            )
        entries = select_skill_folder_files(tree, skill_md_path)

        bundle_size = skill_md_size + sum(entry.get("size", 0) for entry in entries)
        if bundle_size > MAX_SKILL_BUNDLE_SIZE:
            logger.warning(
                f"Skipping skill {skill_md_path} in {organization}/{repo_name}@{ref}: "
                f"SKILL.md and its {len(entries)} folder files total {bundle_size} bytes, "
                f"over the {MAX_SKILL_BUNDLE_SIZE} byte limit"
            )
            return None

        contents = await self._fetch_file_contents(
            organization, repo_name, ref, entries
        )
        return [
            SkillFile(path=path.removeprefix(prefix), content=content)
            for path, content in sorted(contents.items())
        ]

    async def _get_skill_folder_tree(
        self, organization: str, repo_name: str, ref: str, prefix: str
    ) -> list[dict[str, Any]]:
        """The skill folder's own tree with repo-relative paths.

        Used when GitHub truncates the whole-repo tree: a single folder stays far
        below the limit, so its listing is complete.
        """
        folder_tree, _ = await self.get_tree_recursive(
            organization, repo_name, f"{ref}:{prefix.rstrip('/')}"
        )
        return [{**entry, "path": f"{prefix}{entry['path']}"} for entry in folder_tree]

    async def _fetch_file_contents(
        self,
        organization: str,
        repo_name: str,
        ref: str,
        entries: list[dict[str, Any]],
    ) -> dict[str, str]:
        """Fetch raw contents keyed by repo path: small files in batched GraphQL
        queries, larger ones through the REST contents API."""
        graphql_files = []
        rest_files = []
        for entry in entries:
            file_info = {
                "organization": organization,
                "repo_name": repo_name,
                "file_path": entry["path"],
                "skip_parsing": True,
                "branch": ref,
                "sha": entry.get("sha"),
            }
            fetch_method = determine_api_client_type_by_file_size(entry.get("size", 0))
            if fetch_method == GithubClientType.GRAPHQL:
                graphql_files.append(file_info)
            else:
                rest_files.append(file_info)

        contents: dict[str, str] = {}
        async for batch in self.process_graphql_files(graphql_files):
            contents.update({file["path"]: file["content"] for file in batch})
        if rest_files:
            async for batch in self.process_rest_api_files(rest_files):
                contents.update({file["path"]: file["content"] for file in batch})
        return contents
