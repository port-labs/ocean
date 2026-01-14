import asyncio
import os
from typing import Optional


def is_container() -> bool:
    """Detect if running inside Docker/container."""
    if os.path.exists("/.dockerenv"):
        return True
    try:
        with open("/proc/1/cgroup", "r") as f:
            content = f.read()
            if any(x in content for x in ["docker", "kubepods", "containerd"]):
                return True
    except (FileNotFoundError, PermissionError):
        pass
    return False


def _read_cgroup(path: str) -> Optional[int]:
    """Read integer from cgroup file."""
    try:
        with open(path, "r") as f:
            val = f.read().strip()
            return None if val == "max" else int(val)
    except (FileNotFoundError, PermissionError, ValueError):
        return None


async def measure_event_loop_latency() -> float:
    """
    Measure event loop latency in milliseconds.

    Schedules a callback and measures how long it takes to execute.
    High latency indicates blocking operations in the event loop.
    """
    loop = asyncio.get_event_loop()
    start = loop.time()

    # Yield control and measure how long until we get it back
    await asyncio.sleep(0)

    latency_ms = (loop.time() - start) * 1000
    return latency_ms
