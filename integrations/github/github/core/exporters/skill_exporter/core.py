from typing import Any, List

from loguru import logger

from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.skill_exporter.utils import build_skill_raw_item
from github.core.options import ListFileSearchOptions
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class SkillExporter(RestFileExporter):
    """Discovers SKILL.md files and emits normalized skill entities."""

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
                        sha=file_obj.get("metadata", {}).get("sha"),
                    )
                )
            if skills:
                yield skills
