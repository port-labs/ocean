from .base import BaseExporter


class GenericExporter(BaseExporter):
    def __init__(
        self, name: str, sp_path: str, blueprint: str, mapping_fn, client, cfg
    ):
        super().__init__(client, mapping=None, cfg=cfg)
        self.kind = name
        self.sp_path = sp_path
        self.blueprint = blueprint
        self._map = mapping_fn

    async def ingest(self, ocean):
        async def produce():
            async for sp in self.fetch():
                yield self._map(sp)

        await ocean.port_client.ingest_entities_stream(
            blueprint=self.blueprint, entities_async_iter=produce()
        )
