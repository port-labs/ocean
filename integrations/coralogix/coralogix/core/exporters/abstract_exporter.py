from abc import ABC, abstractmethod
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from coralogix.clients.client import CoralogixClient
from coralogix.helpers.exceptions import CoralogixApiError
from coralogix.helpers.utils import MGMT_API_PREFIX

TEAM_URL_KEY = "__teamUrl"


class AbstractCoralogixExporter[T: CoralogixClient](ABC):
    def __init__(self, client: T) -> None:
        self.client = client

    @abstractmethod
    def get_paginated_resources[
        Options: Any
    ](self, options: Options) -> ASYNC_GENERATOR_RESYNC_TYPE: ...

    @abstractmethod
    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]: ...

    async def get_team_url(self) -> str:
        """Web app URL of the key's team, used to build links back to Coralogix."""
        identity = await self.client.send_api_request(
            f"{MGMT_API_PREFIX}/aaa/identity/v1/whoami"
        )
        team_url = identity.get("teamUrl")
        if not isinstance(team_url, str) or not team_url.strip():
            raise CoralogixApiError(
                "Coralogix whoami did not return a team URL, so catalog links "
                "cannot be built."
            )
        return team_url.strip().rstrip("/")

    @staticmethod
    def with_team_url(items: list[RAW_ITEM], team_url: str) -> list[RAW_ITEM]:
        return [{**item, TEAM_URL_KEY: team_url} for item in items]
