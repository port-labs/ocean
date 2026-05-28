from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from core.exporters.abstract_exporter import AbstractClaudeExporter
from core.options import ListClaudeUserActivityOptions


class ClaudeUserActivityExporter(AbstractClaudeExporter):
    async def get_paginated_resources(
        self, options: ListClaudeUserActivityOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        params = {
            "date": options["date"],
            "limit": options["limit"],
        }

        date = options["date"]
        async for batch in self.client.get_user_activity(params):
            logger.debug(f"Fetched user activity batch with {len(batch)} records")
            # Inject the query date so the Port mapping can build unique identifiers.
            # The /users endpoint does not include the date in each record.
            yield [{**record, "__date": date} for record in batch]
