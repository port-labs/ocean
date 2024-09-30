from asyncio import gather
from typing import Any, Dict, List

from port_ocean.context.ocean import ocean

from fake_org_data.fake_client import get_fake_persons
from fake_org_data.static import FAKE_DEPARTMENTS
from fake_org_data.fake_router import initialize_fake_routes


@ocean.on_resync("fake-department")
async def resync_department(kind: str) -> List[Dict[Any, Any]]:
    return [f.dict() for f in FAKE_DEPARTMENTS]


@ocean.on_resync("fake-person")
async def resync_persons(kind: str) -> List[Dict[Any, Any]]:
    tasks = []
    for department in FAKE_DEPARTMENTS:
        tasks.append(get_fake_persons(department))

    result = await gather(*tasks)
    persons = []
    for persons_per_department in result:
        for person in persons_per_department:
            persons.append(person.dict())

    return persons


@ocean.on_start()
async def on_start() -> None:
    print("Starting fake integration!")
    initialize_fake_routes()
