from typing import Any, List, Dict
from asyncio import gather

from port_ocean.context.ocean import ocean

from punny.static import PUN_CATEGORIES
from punny.pun_client import get_puns


@ocean.on_resync("dummy-category")
async def resync_category(kind: str) -> list[dict[Any, Any]]:
    return [f.dict() for f in PUN_CATEGORIES]


@ocean.on_resync("dummy-joke")
async def resync_puns(kind: str) -> List[Dict[Any, Any]]:
    tasks = []
    for category in PUN_CATEGORIES:
        tasks.append(get_puns(category))

    result = await gather(*tasks)
    jokes = []
    for jokes_per_category in result:
        for joke in jokes_per_category:
            jokes.append(joke.dict())

    return jokes


@ocean.on_start()
async def on_start() -> None:
    print("Starting dummy pun integration!")
