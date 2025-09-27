from typing import Any, AsyncIterator, Dict

from .base import BaseExporter


class SourcesExporter(BaseExporter):
    kind = "source"
    sp_path = "/v2025/sources"
    blueprint = "sailpoint_source"

    def default_params(self) -> Dict[str, Any]:
        params = super().default_params()
        fcfg = self.cfg.filters
        raw = (fcfg.raw.get("sources") or {}).copy()

        # if fcfg.sources_type: raw["type"] = fcfg.sources_type
        # if fcfg.sources_updated_since_days: raw["updatedSince"] = fcfg.sources_updated_since_days
        # if fcfg.sources_authoritative: raw["authoritative"] = fcfg.sources_authoritative
        # if fcfg.sources_status: raw["status"] = fcfg.sources_status

        raw.setdefault("limit", self.cfg.runtime.page_size)
        return raw

    async def ingest(self, ocean) -> None:
        mapping = self.mapping

        async def produce() -> AsyncIterator[Dict[str, Any]]:
            async for sp in self.fetch():
                yield mapping.map_source(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
