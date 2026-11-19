from __future__ import annotations

from http import HTTPStatus

import httpx
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


def _is_forbidden(error: httpx.HTTPStatusError) -> bool:
    return (
        error.response is not None
        and error.response.status_code == HTTPStatus.FORBIDDEN
    )


class SessionExporter(AbstractFactoryExporter[ListSessionOptions, GetSessionOptions]):
    """Sync Factory Droid sessions.

    Soft-fails (yields nothing / returns ``None``) on HTTP 403 when the org
    lacks Sessions API access, so the rest of the resync can still reconcile.
    """

    async def get_paginated_resources(
        self, options: ListSessionOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        cursor: str | None = None
        while True:
            params = options.to_query_params()
            if cursor:
                params["cursor"] = cursor

            try:
                response = await self.client.get(
                    _SESSIONS_PATH,
                    ListSessionsResponse,
                    params=params or None,
                )
            except httpx.HTTPStatusError as error:
                if _is_forbidden(error):
                    logger.warning(
                        "Factory Sessions API returned 403; org likely lacks "
                        "access. Skipping session sync."
                    )
                    return
                raise

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

        try:
            session = await self.client.get_or_none(
                f"{_SESSIONS_PATH}/{options.session_id}",
                Session,
                params=params,
            )
        except httpx.HTTPStatusError as error:
            if _is_forbidden(error):
                logger.warning(
                    "Factory Sessions API returned 403; org likely lacks "
                    "access. Skipping session lookup."
                )
                return None
            raise
        return session.to_raw_item() if session else None
