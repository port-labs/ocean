from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from claude_managed_agents.core.archived_resources import ArchivedResourceChecker
from claude_managed_agents.core.exporters.abstract_exporter import (
    AbstractAnthropicExporter,
)


class SessionsExporter(AbstractAnthropicExporter):
    async def get_paginated_resources(
        self,
        *,
        include_archived: bool = False,
        include_sessions_of_archived_resources: bool = True,
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        checker: ArchivedResourceChecker | None = None
        if not include_sessions_of_archived_resources:
            checker = ArchivedResourceChecker(self.client)
            await checker.load_archived_ids()

        async for batch in self.client.paginate(
            self.client.beta.sessions.list(include_archived=include_archived)
        ):
            logger.debug(f"Fetched sessions batch with {len(batch)} records")
            sessions = [item.to_dict(mode="json", warnings=False) for item in batch]

            if checker is None:
                yield sessions
                continue

            kept = [
                session
                for session in sessions
                if not await checker.session_references_archived_resource(session)
            ]
            if len(kept) != len(sessions):
                logger.info(
                    f"Skipped {len(sessions) - len(kept)} sessions that reference "
                    "archived resources"
                )
            yield kept
