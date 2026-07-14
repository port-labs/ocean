from typing import Any, List, Optional

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.skill_exporter.utils import (
    DEFAULT_SKILL_ROOTS,
    SkillContentMode,
    build_skill_raw_item,
    roots_to_globs,
)
from github.core.options import ListFileSearchOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class SkillExporter(AbstractGithubExporter[GithubRestClient]):
    """Discovers SKILL.md files and emits normalized skill entities."""

    def __init__(self, client: GithubRestClient) -> None:
        super().__init__(client)
        self._file_exporter = RestFileExporter(client)

    async def get_resource(self, options: Any) -> RAW_ITEM:
        raise NotImplementedError("SkillExporter does not support get_resource")

    async def get_paginated_resources(
        self, options: List[ListFileSearchOptions]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError("Use get_paginated_skills")

    async def get_paginated_skills(
        self,
        repo_path_map: List[ListFileSearchOptions],
        *,
        content_mode: SkillContentMode,
        roots: list[str],
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for file_batch in self._file_exporter.get_paginated_resources(
            repo_path_map
        ):
            skills: list[dict[str, Any]] = []
            for file_obj in file_batch:
                content = file_obj.get("content")
                if not isinstance(content, str):
                    logger.warning(
                        f"Skipping skill file {file_obj.get('path')} — "
                        "content is not a string"
                    )
                    continue
                skills.append(
                    build_skill_raw_item(
                        skill_md_path=file_obj["path"],
                        content=content,
                        content_mode=content_mode,
                        repository=file_obj["repository"],
                        branch=file_obj["branch"],
                        organization=file_obj.get("organization"),
                        roots=roots,
                    )
                )
            if skills:
                yield skills


def build_skill_file_patterns(
    *,
    roots: list[str],
    paths: list[str],
    organization: Optional[str],
    repos: Optional[list[Any]],
) -> list[Any]:
    """Build GithubFilePattern objects for FilePatternMappingBuilder."""
    from integration import GithubFilePattern

    effective_roots = roots or list(DEFAULT_SKILL_ROOTS)
    globs = roots_to_globs(effective_roots) + list(paths)
    return [
        GithubFilePattern(
            path=glob_path,
            organization=organization,
            repos=repos,
            skipParsing=True,
            validationCheck=False,
        )
        for glob_path in globs
    ]
