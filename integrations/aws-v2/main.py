from typing import Any

from port_ocean.context.ocean import ocean
from aws.resync_factory import resync, CloudControlResyncHandler
from aws.auth.account import SessionStrategyFactory


@ocean.on_resync()
async def on_resync_all(kind: str) -> list[dict[Any, Any]]:
    ctx = ResyncContext(kind=kind)
    strategy = SessionStrategyFactory()
    handler = CloudControlResyncHandler(
        context=ctx,
        credentials=AWSSessionStrategy(),
    )
    async for batch in handler:
        yield batch


# Listen to the start event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    print("Starting aws_v2 integration")
