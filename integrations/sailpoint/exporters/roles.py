from typing import Any, AsyncIterator, Dict

from .base import BaseExporter


class RolesExporter(BaseExporter):
    kind = "role"
    sp_path = "/v2025/roles"
    blueprint = "sailpoint_role"

    def default_params(self) -> Dict[str, Any]:
        params = super().default_params()
        fcfg = self.cfg.filters
        raw = (fcfg.raw.get("roles") or {}).copy()
        # if fcfg.roles_status: raw["status"] = fcfg.roles_status
        # if fcfg.roles_type: raw["type"] = fcfg.roles_type
        # if fcfg.roles_updated_since_days: raw["updatedSince"] = fcfg.roles_updated_since_days

        raw.setdefault("limit", self.cfg.runtime.page_size)
        return raw

    async def ingest(self, ocean) -> None:
        mapping = self.mapping

        async def produce() -> AsyncIterator[Dict[str, Any]]:
            async for sp in self.fetch():
                yield mapping.map_role(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
