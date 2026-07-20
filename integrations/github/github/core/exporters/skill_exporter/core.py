from typing import Any, List

from loguru import logger

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.skill_exporter.utils import build_skill_raw_item
from github.core.options import ListFileSearchOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM


class SkillExporter(AbstractGithubExporter[GithubRestClient]):
    """Discovers SKILL.md files and emits normalized skill entities."""

    def __init__(self, client: GithubRestClient) -> None:
        super().__init__(client)
        self._file_exporter = RestFileExporter(client)

    async def get_resource(self, options: Any) -> RAW_ITEM:
        raise NotImplementedError("SkillExporter does not support get_resource")

    def get_paginated_resources(
        self, options: List[ListFileSearchOptions]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        raise NotImplementedError("Use get_paginated_skills")

    async def get_paginated_skills(
        self,
        repo_path_map: List[ListFileSearchOptions],
        *,
        path_globs: list[str],
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
                        repository=file_obj["repository"],
                        branch=file_obj["branch"],
                        organization=file_obj.get("organization"),
                        path_globs=path_globs,
                    )
                )
            if skills:
                yield skills
