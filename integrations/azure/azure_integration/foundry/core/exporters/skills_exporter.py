from __future__ import annotations

from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.core.incremental.strategies import paginate_with_strategy
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from azure_integration.foundry.core.exporters.base import FoundryExporter
from azure_integration.foundry.core.options import ListSkillsOptions
from azure_integration.foundry.foundry_incremental import SKILL_INCREMENTAL
from azure_integration.foundry.helpers.utils import enrich_with_project

_SKILLS_FEATURE = "Skills=V1Preview"


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
            yield [
                enrich_with_project(
                    item,
                    project_endpoint=project_endpoint,
                    project_id=project_id,
                )
                for item in page
            ]
