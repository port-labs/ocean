from .base import BaseExporter


class IdentitiesExporter(BaseExporter):
    kind = "identity"
    sp_path = "/v2025/identities"
    blueprint = "sailpoint_identity"

    def default_params(self):
        params = super().default_params()
        fcfg = self.cfg.filters
        raw = (fcfg.raw.get("identities") or {}).copy()

        if fcfg.identities_status:
            raw["status"] = fcfg.identities_status
        if fcfg.identities_updated_since_days:
            raw["updatedSince"] = fcfg.identities_updated_since_days

        raw.setdefault("limit", self.cfg.runtime.page_size)
        return raw

    async def ingest(self, ocean):
        async def produce():
            async for sp in self.fetch():
                yield self.mapping.map_identity(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
