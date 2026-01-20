import asyncio


async def measure_event_loop_latency() -> float:
    """
    Measure event loop latency in milliseconds.

    Schedules a callback and measures how long it takes to execute.
    High latency indicates blocking operations in the event loop.
    """
    loop = asyncio.get_running_loop()
    start = loop.time()

    # Yield control and measure how long until we get it back
    await asyncio.sleep(0)

    latency_ms = (loop.time() - start) * 1000
    return latency_ms
