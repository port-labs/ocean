from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from coralogix.clients.client import CoralogixClient, PaginationStyle
from coralogix.core.exporters.abstract_exporter import AbstractCoralogixExporter
from coralogix.helpers.utils import MGMT_API_PREFIX

ALERTS_ENDPOINT = f"{MGMT_API_PREFIX}/alerts/alerts/v3"


class AlertDefinitionExporter(AbstractCoralogixExporter[CoralogixClient]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        team_url = await self.get_team_url()
        async for alerts in self.client.send_paginated_request(
            ALERTS_ENDPOINT, data_key="alertDefs", style=PaginationStyle.TOKEN_QUERY
        ):
            yield self.with_team_url(alerts, team_url)

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(
            f"{ALERTS_ENDPOINT}/{resource_id}"
        )
        return response.get("alertDef") or None
