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


@ocean.on_resync(ObjectKind.CUSTOMER)
async def on_resync_customers(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = PlainClient()
    async for customers in client.get_customers():
        logger.info(f"Received customer batch with {len(customers)} customers")
        yield customers


@ocean.on_resync(ObjectKind.THREAD)
async def on_resync_threads(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = PlainClient()
    async for threads in client.get_threads():
        logger.info(f"Received thread batch with {len(threads)} threads")
        yield threads


def _live_events_enabled() -> bool:
    raw = ocean.integration_config.get("enable_live_events", False)
    if isinstance(raw, str):
        return raw.strip().lower() in {"1", "true", "yes", "on"}
    return bool(raw)


async def _register_webhook_target() -> None:
    # TODO Phase 2 (P2-T5): create the Plain webhook target and point it at this integration.
    logger.info(
        "Plain live events are enabled; webhook registration is not implemented yet"
    )


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting plain integration")
    if not _live_events_enabled():
        logger.info("Plain live events are disabled; skipping webhook registration")
        return
    await _register_webhook_target()
