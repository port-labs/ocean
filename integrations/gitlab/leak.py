import tracemalloc
import asyncio
from loguru import logger


logger.add("leakfile.log", rotation="10 MB")


async def periodic_memory_snapshot(interval: float = 30.0):
    tracemalloc.start()
    while True:
        await asyncio.sleep(interval)
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics("lineno")
        logger.info("Top memory allocations:")
        for stat in top_stats[:10]:
            logger.info(stat)
