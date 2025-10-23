from typing import Any, AsyncIterator, Dict

from .base import BaseExporter


class EntitlementsExporter(BaseExporter):
    kind = "entitlement"
    sp_path = "/v2025/entitlements"
    blueprint = "sailpoint_entitlement"

    def default_params(self) -> Dict[str, Any]:
        params = super().default_params()
        fcfg = self.cfg.filters
        raw = (fcfg.raw.get("entitlements") or {}).copy()

        if fcfg.entitlements_name_contains:
            raw["nameContains"] = fcfg.entitlements_name_contains
        if fcfg.entitlements_name_startswith:
            raw["nameStartsWith"] = fcfg.entitlements_name_startswith

        if getattr(fcfg, "accounts_source_id", None):
            raw.setdefault("sourceId", fcfg.accounts_source_id)

        raw.setdefault("limit", self.cfg.runtime.page_size)
        return raw

    async def ingest(self, ocean) -> None:
        mapping = self.mapping

        async def produce() -> AsyncIterator[Dict[str, Any]]:
            async for sp in self.fetch():
                yield mapping.map_entitlement(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
