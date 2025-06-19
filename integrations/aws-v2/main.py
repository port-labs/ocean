from typing import Any

from port_ocean.context.ocean import ocean
from aws.resync_factory import resync, CloudControlResyncHandler

session_strategy = None


async def resync_resources(kind: str) -> AsyncIterator[MaterializedResource]:
    async for account in session_strategy.get_accessible_accounts():
        async for session in session_strategy.create_session_for_each_region():
            handler = CloudControlResyncHandler(
                kind=kind,
                credentials=session_strategy,
                use_get_resource_api=ocean.integration_config.get(
                    "use_get_resource_api", False
                ),
                batch_size=ocean.integration_config.get("batch_size", 10),
            )

            async with handler:
                async for resource_batch in handler:
                    for resource in resource_batch:
                        yield resource


@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[str, Any]]:
    resources = []

    async for materialized_resource in resync_resources(kind):
        resources.append(materialized_resource)

    ocean.logger.info(f"Resynced {len(resources)} resources of kind '{kind}'")

    return resources


@ocean.on_before_resync()
async def on_before_resync() -> None:
    global session_strategy
    session_strategy_factory = SessionStrategyFactory(ocean.credentials_provider)
    session_strategy = await session_strategy_factory(selector=ocean.resource_config)
