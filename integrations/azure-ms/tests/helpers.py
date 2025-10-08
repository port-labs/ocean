from typing import Any, AsyncGenerator, Iterable


# Utility for mocking async generators
def aiter(iterable: Iterable[Any]) -> AsyncGenerator[Any, Any]:
    async def gen() -> AsyncGenerator[Any, Any]:
        for item in iterable:
            yield item

    return gen()
