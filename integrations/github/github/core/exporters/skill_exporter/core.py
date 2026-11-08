from typing import Any, Dict, List

from loguru import logger

from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.skill_exporter.utils import build_skill_raw_item
from github.core.options import ListFileSearchOptions


class SkillExporter(RestFileExporter):
    """Discovers SKILL.md files and emits normalized skill entities."""

    def _transform_batch(
        self, files: List[Dict[str, Any]], options: List[ListFileSearchOptions]
    ) -> List[Dict[str, Any]]:
        path_globs = list(
            dict.fromkeys(
                file_options["path"]
                for repo_options in options
                for file_options in repo_options["files"]
            )
        )
        skills: List[Dict[str, Any]] = []
        for file_obj in files:
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
                    blob_sha=file_obj.get("metadata", {}).get("sha"),
                )
            )
        return skills
