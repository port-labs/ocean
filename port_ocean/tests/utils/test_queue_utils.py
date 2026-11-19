import asyncio

import pytest

from port_ocean.utils.queue_utils import process_in_queue


async def _identity(value: int) -> int:
    return value


@pytest.mark.parametrize("concurrency", [0, -1])
async def test_process_in_queue_rejects_non_positive_concurrency(
    concurrency: int,
) -> None:
    with pytest.raises(ValueError, match="concurrency must be at least 1"):
        await asyncio.wait_for(
            process_in_queue([1, 2, 3], _identity, concurrency=concurrency),
            timeout=1,
        )
