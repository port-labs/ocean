from typing import Any, AsyncIterator, Dict

from .base import BaseExporter


class AccountsExporter(BaseExporter):
    kind = "account"
    sp_path = "/v2025/accounts"
    blueprint = "sailpoint_account"

    def default_params(self) -> Dict[str, Any]:
        params = super().default_params()
        fcfg = self.cfg.filters
        raw = (fcfg.raw.get("accounts") or {}).copy()

        if fcfg.accounts_source_id:
            raw["sourceId"] = fcfg.accounts_source_id

        raw.setdefault("limit", self.cfg.runtime.page_size)
        return raw

    async def ingest(self, ocean) -> None:
        mapping = self.mapping

        async def produce() -> AsyncIterator[Dict[str, Any]]:
            async for sp in self.fetch():
                yield mapping.map_account(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
