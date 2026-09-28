from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import ExampleKind
from plain.client import PlainClient
from plain.utils import ObjectKind


@ocean.on_resync(ExampleKind.EXAMPLE_KIND)
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    if kind == ExampleKind.EXAMPLE_KIND:
        return [
            {
                "my_custom_id": f"id_{x}",
                "my_custom_text": f"very long text with {x} in it",
                "my_special_score": x * 32 % 3,
                "my_component": f"component-{x}",
                "my_service": f"service-{x %2}",
                "my_enum": "VALID" if x % 2 == 0 else "FAILED",
            }
            for x in range(25)
        ]

    return []


@ocean.on_resync(ObjectKind.COMPANY)
async def on_resync_companies(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = PlainClient()
    async for companies in client.get_companies():
        logger.info(f"Received company batch with {len(companies)} companies")
        yield companies


@ocean.on_resync(ObjectKind.TENANT)
async def on_resync_tenants(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = PlainClient()
    async for tenants in client.get_tenants():
        logger.info(f"Received tenant batch with {len(tenants)} tenants")
        yield tenants


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = PlainClient()
    async for users in client.get_users():
        logger.info(f"Received user batch with {len(users)} users")
        yield users


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting plain integration")
