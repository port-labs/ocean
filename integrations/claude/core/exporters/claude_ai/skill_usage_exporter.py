from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListSkillUsageOptions


class ClaudeAISkillUsageExporter(AbstractClaudeExporter):
    """Skill usage metrics for a single day (Claude AI / Enterprise).

    The skills endpoint reports one day at a time and does not echo the queried
    date back in each row, so the date is injected onto every record to allow a
    stable per-skill-per-day identifier downstream. Optional ``group_by``
    dimensions (user_id, product, rbac_group_id) are forwarded as ``group_by[]``.
    """

    ENDPOINT = "/v1/organizations/analytics/skills"

    async def get_paginated_resources(
        self, options: ListSkillUsageOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        date = options["date"]
        params: dict[str, object] = {
            "date": date,
            "limit": options["limit"],
        }

        group_by = options.get("group_by", [])
        if group_by:
            params["group_by[]"] = group_by

        async for batch in self.client.send_paginated_request(
            self.ENDPOINT, params, soft_fail_statuses={403}
        ):
            for record in batch:
                record["__date"] = date
            logger.debug(
                f"Fetched skill usage batch with {len(batch)} records for {date}"
            )
            yield batch
