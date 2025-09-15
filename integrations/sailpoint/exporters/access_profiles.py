from typing import Any, Dict

from .base import BaseExporter


class AccessProfilesExporter(BaseExporter):
    kind = "access_profile"
    sp_path = "/v2025/access-profiles"
    blueprint = "sailpoint_access_profile"

    def default_params(self) -> Dict[str, Any]:
        params = super().default_params()
        fcfg = self.cfg.filters
        raw = (fcfg.raw.get("access_profiles") or {}).copy()

        raw.setdefault("limit", self.cfg.runtime.page_size)
        return raw

    async def ingest(self, ocean) -> None:
        mapping = self.mapping

        async def produce():
            async for sp in self.fetch():
                yield mapping.map_access_profile(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
