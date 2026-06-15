from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListUserActivityOptions


class ClaudeAIUserActivityExporter(AbstractClaudeExporter):
    """Per-user engagement metrics for a single day (Claude AI / Enterprise).

    The users endpoint reports one day at a time and does not echo the queried
    date back in each row, so the date is injected onto every record to allow a
    stable per-user-per-day identifier downstream.
    """

    ENDPOINT = "/v1/organizations/analytics/users"

    async def get_paginated_resources(
        self, options: ListUserActivityOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        date = options["date"]
        params = {
            "date": date,
            "limit": options["limit"],
        }

        async for batch in self.client.send_paginated_request(
            self.ENDPOINT, params, soft_fail_statuses={403}
        ):
            for record in batch:
                record["__date"] = date
            logger.debug(
                f"Fetched user activity batch with {len(batch)} records for {date}"
            )
            yield batch
