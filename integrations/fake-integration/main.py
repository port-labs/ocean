from datetime import datetime
from typing import Any

from fastapi import Request
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from loguru import logger

from fake_org_data.fake_client import (
    get_departments,
    get_fake_persons,
    get_offices,
    get_projects,
    get_random_person_from_batch,
    get_teams,
)
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from fake_org_data.fake_router import initialize_fake_routes


# ---------------------------------------------------------------------------
# Full resync handlers
# All kinds register both on_resync and on_incremental_resync in the same file.
# In production both run from the same Docker image — the entry point determines
# which sync method (sync_raw_all vs sync_incremental) is called, and each
# method only uses its own event_strategy dict, so they never interfere.
# ---------------------------------------------------------------------------

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


@ocean.on_resync("fake-office")
async def resync_offices(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for office_batch in get_offices():
        logger.info(f"Got a batch of {len(office_batch)} offices")
        yield office_batch


@ocean.on_resync("fake-team")
async def resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for team_batch in get_teams():
        logger.info(f"Got a batch of {len(team_batch)} teams")
        yield team_batch


@ocean.on_resync("fake-project")
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    async for project_batch in get_projects():
        logger.info(f"Got a batch of {len(project_batch)} projects")
        yield project_batch


# ---------------------------------------------------------------------------
# Incremental resync handlers
# ---------------------------------------------------------------------------

@ocean.on_incremental_resync("fake-department")
async def incremental_resync_departments(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    cursor: datetime | None = event.attributes.get("incremental_cursor")
    logger.info(
        "Incremental handler invoked for fake-department",
        cursor=cursor.isoformat() if cursor else "none (first run)",
    )
    # Departments are a small, slow-changing set — always return all of them.
    # In a real integration the API would filter by the cursor server-side.
    async for batch in get_departments():
        logger.info("Yielding departments batch (incremental)", count=len(batch))
        yield batch


@ocean.on_incremental_resync("fake-office")
async def incremental_resync_offices(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    cursor: datetime | None = event.attributes.get("incremental_cursor")
    logger.info(
        "Incremental handler invoked for fake-office",
        cursor=cursor.isoformat() if cursor else "none (first run)",
    )
    # Same as departments — small set, always return all.
    async for batch in get_offices():
        logger.info("Yielding offices batch (incremental)", count=len(batch))
        yield batch


@ocean.on_incremental_resync("fake-person")
async def incremental_resync_persons(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    cursor: datetime | None = event.attributes.get("incremental_cursor")
    logger.info(
        "Incremental handler invoked for fake-person",
        cursor=cursor.isoformat() if cursor else "none (first run)",
    )
    async for persons_batch in get_fake_persons():
        if cursor is not None:
            # In a real integration this filter would be an API param (e.g. since=<cursor>).
            # Here we simulate server-side filtering client-side by dropping stale items.
            persons_batch = [
                p for p in persons_batch if p.get("updatedAt", "") >= cursor.isoformat()
            ]
        logger.info(
            "Yielding persons batch (incremental)",
            count=len(persons_batch),
            cursor=cursor.isoformat() if cursor else "none",
        )
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
    logger.info("Starting fake integration!")
