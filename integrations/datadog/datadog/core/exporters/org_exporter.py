from typing import TYPE_CHECKING, Any

from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from datadog.core.exporters.base_exporter import (
    GetOptions,
    PaginatedExporter,
    SingleResourceExporter,
)

if TYPE_CHECKING:
    from datadog.overrides import OrgResourceConfig


class GetOrgOptions(GetOptions["OrgResourceConfig"]):
    @classmethod
    def from_resource_config(
        cls, resource_config: "OrgResourceConfig", *, resource_id: str
    ) -> "GetOrgOptions":
        return cls(resource_id=resource_id)


class OrgExporter(PaginatedExporter[None], SingleResourceExporter[GetOrgOptions]):
    async def get_paginated_resources(
        self, options: None = None
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Get organizations from Datadog.
        The list endpoint returns all managed organizations in a single
        non-paginated response under the ``orgs`` key.
        Docs: https://docs.datadoghq.com/api/latest/organizations/#list-your-managed-organizations
        """
        url = f"{self.client.api_url}/api/v1/org"
        result = await self.client.send_api_request(url)
        orgs = result.get("orgs") or []
        if orgs:
            yield orgs

    async def get_resource(self, options: GetOrgOptions) -> dict[str, Any] | None:
        """Get a single organization by its public ID.
        Returns the org under the ``org`` key, matching the shape of each item
        in the list response.
        Docs: https://docs.datadoghq.com/api/latest/organizations/#get-organization-information
        """
        url = f"{self.client.api_url}/api/v1/org/{options.resource_id}"
        result = await self.client.send_api_request(url)
        return result.get("org")
