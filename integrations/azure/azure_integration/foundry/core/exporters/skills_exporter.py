from __future__ import annotations

import io
import zipfile
from functools import partial
from pathlib import PurePosixPath
from typing import Any

from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from port_ocean.utils.async_iterators import throttle_batch_operation

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListSkillsOptions
from azure_integration.foundry.foundry_incremental import SKILL_INCREMENTAL
from azure_integration.foundry.helpers.utils import (
    build_foundry_url,
    enrich_with_project,
)

_SKILLS_FEATURE = "Skills=V1Preview"
_CONTENT_HEADERS = {
    "Foundry-Features": _SKILLS_FEATURE,
    "Accept": "application/zip",
}
# ponytail: concurrency 5; raise if Foundry rate limits allow more
_CONTENT_CONCURRENCY = 5


def skill_markdown_from_zip(payload: bytes) -> str | None:
    if not payload:
        return None
    try:
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            candidates = [
                name
                for name in archive.namelist()
                if PurePosixPath(name).name.lower() == "skill.md"
            ]
            if not candidates:
                return None
            candidates.sort(key=lambda name: name.count("/"))
            return archive.read(candidates[0]).decode("utf-8")
    except (zipfile.BadZipFile, UnicodeDecodeError, KeyError, OSError):
        return None


class SkillsExporter(FoundryExporter):
    async def get_paginated_resources(
        self, options: ListSkillsOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        project_endpoint = options.project_endpoint
        project_id = options.project_id
        cursor = active_incremental_cursor()
        params = SKILL_INCREMENTAL.merge_params({}, cursor)
        headers = {"Foundry-Features": _SKILLS_FEATURE}

        async for page in paginate_with_strategy(
            self.client.send_cursor_paginated_request(
                project_endpoint,
                "skills",
                params=params,
                extra_headers=headers,
            ),
            cursor=cursor,
            strategy=SKILL_INCREMENTAL,
        ):
            batch = [
                enrich_with_project(
                    item,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
            await throttle_batch_operation(
                [
                    partial(self._load_skill_markdown, project_endpoint, skill)
                    for skill in batch
                ],
                concurrency=_CONTENT_CONCURRENCY,
            )
            yield batch

    async def _load_skill_markdown(
        self,
        project_endpoint: str,
        skill: dict[str, Any],
    ) -> None:
        name = skill.get("name")
        if not name:
            return
        try:
            raw = await self.client.send_bytes_request(
                build_foundry_url(project_endpoint, f"skills/{name}/content"),
                extra_headers=_CONTENT_HEADERS,
            )
        except FoundryApiError as exc:
            logger.warning(
                f"Skipping skill content for {name}: {exc}",
                project_endpoint=project_endpoint,
            )
            return
        markdown = skill_markdown_from_zip(raw)
        if markdown is not None:
            skill["__skillMarkdown"] = markdown
