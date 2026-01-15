from dataclasses import dataclass
from typing import Any


@dataclass
class ResourceUsageStats:
    """Statistics for resource usage metrics (CPU, memory, latency, request size)."""

    cpu_max: float = 0.0
    cpu_median: float = 0.0
    cpu_avg: float = 0.0
    memory_max: int = 0
    memory_median: int = 0
    memory_avg: int = 0
    latency_max: float = 0.0
    latency_median: float = 0.0
    latency_avg: float = 0.0
    response_size_total: int = 0
    response_size_avg: float = 0.0
    response_size_median: float = 0.0
    request_count: int = 0  # Number of HTTP responses made
    sample_count: int = 0


@dataclass
class ProcessNode:
    """A node in the process tree - represents one process with its children."""

    cpu_percent: float
    memory_rss: int  # Resident Set Size in bytes
    children: list[dict[str, Any]]  # List of ProcessNode as dicts (recursive)


@dataclass
class SystemSnapshot:
    """System metrics snapshot - only the fields actually used for tracking."""

    process_cpu_percent: float
    process_memory_rss: int  # Total RSS memory in bytes
    event_loop_latency_ms: float  # How responsive is the async event loop
