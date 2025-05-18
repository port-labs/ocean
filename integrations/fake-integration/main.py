from typing import Any

from fastapi import Request
from port_ocean.context.ocean import ocean
from loguru import logger

from fake_org_data.fake_client import (
    get_fake_persons,
    get_departments,
    get_random_person_from_batch,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from fake_org_data.fake_router import initialize_fake_routes


@ocean.on_resync("fake-department")
async def resync_department(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for department_batch in get_departments():
        logger.info(f"Got a batch of {len(department_batch)} departments")
        yield department_batch


@ocean.on_resync("fake-person")
async def resync_persons(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for persons_batch in get_fake_persons():
        logger.info(f"Got a batch of {len(persons_batch)} persons")
        yield persons_batch


initialize_fake_routes()


@ocean.router.post("/webhook")
async def webhook_handler(request: Request) -> dict[str, Any]:
    logger.info("Received a webhook!")
    person = await get_random_person_from_batch()
    await ocean.register_raw("fake-person", [person])
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    print("Starting fake integration!")
