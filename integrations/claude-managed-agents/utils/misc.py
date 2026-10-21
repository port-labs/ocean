from typing import AsyncIterator, Callable
from typing import TypeVar

T = TypeVar("T")


async def find_first_item_in_generator(
    generator: AsyncIterator[list[T]],
    match: Callable[[T], bool],
) -> T | None:
    async for batch in generator:
        for item in batch:
            if match(item):
                return item
    return None
