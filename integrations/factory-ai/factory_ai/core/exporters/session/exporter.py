from __future__ import annotations

from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from factory_ai.core.exporters.abstract_exporter import AbstractFactoryExporter
from factory_ai.core.exporters.session.models import (
    GetSessionOptions,
    ListSessionOptions,
    ListSessionsResponse,
    Session,
)

_SESSIONS_PATH = "/api/v0/sessions"


class SessionExporter(AbstractFactoryExporter[ListSessionOptions, GetSessionOptions]):
    async def get_paginated_resources(
        self, options: ListSessionOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor: str | None = None
        while True:
            params = options.to_query_params()
            if cursor:
                params["cursor"] = cursor

            response = await self.client.get(
                _SESSIONS_PATH,
                ListSessionsResponse,
                params=params or None,
            )
            logger.debug(
                f"Fetched Factory sessions batch with {len(response.sessions)} records"
            )
            yield [session.to_raw_item() for session in response.sessions]

            cursor = response.pagination.next_cursor
            if not cursor:
                break

    async def get_resource(self, options: GetSessionOptions) -> RAW_ITEM | None:
        params: dict[str, str] | None = None
        if options.computer_id:
            params = {"computerId": options.computer_id}

        session = await self.client.get_or_none(
            f"{_SESSIONS_PATH}/{options.session_id}",
            Session,
            params=params,
        )
        return session.to_raw_item() if session else None
