import asyncio
from typing import Any, Optional

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM

from coralogix.clients.client import CoralogixClient
from coralogix.core.exporters.abstract_exporter import AbstractCoralogixExporter
from coralogix.core.options import SloOptions
from coralogix.helpers.exceptions import CoralogixApiError
from coralogix.helpers.utils import MGMT_API_PREFIX

SLOS_ENDPOINT = f"{MGMT_API_PREFIX}/slo/slos/v1"
STATUS_KEY = "__status"
# A single SLO can be listed without a compliance snapshot.
_OPTIONAL_STATUS_CODES = {403, 404}


class SloExporter(AbstractCoralogixExporter[CoralogixClient]):
    async def _with_status(self, slo: RAW_ITEM) -> RAW_ITEM:
        # Ratios 0-1: lowestCompliance, lowestRemainingErrorBudget.
        try:
            status: dict[str, Any] | None = await self.client.send_api_request(
                f"{SLOS_ENDPOINT}/{slo['id']}/status"
            )
        except CoralogixApiError as error:
            if error.status_code not in _OPTIONAL_STATUS_CODES:
                raise
            status = None
        return {**slo, STATUS_KEY: status or None}

    async def get_paginated_resources(
        self, options: SloOptions
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        # The list endpoint is not paginated.
        response = await self.client.send_api_request(SLOS_ENDPOINT)
        slos = response.get("slos", [])
        if not isinstance(slos, list):
            raise CoralogixApiError("Coralogix SLO list was not a list.")
        if not slos:
            return
        if options["include_status"]:
            slos = list(await asyncio.gather(*(self._with_status(s) for s in slos)))
        yield self.with_team_url(slos, await self.get_team_url())

    async def get_single_resource(
        self, resource_id: str, options: Any = None
    ) -> Optional[RAW_ITEM]:
        response = await self.client.send_api_request(f"{SLOS_ENDPOINT}/{resource_id}")
        return response.get("slo") or None
