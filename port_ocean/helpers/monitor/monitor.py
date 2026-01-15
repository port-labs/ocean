"""
Performance Monitor for Ocean Integration Framework.

Tracks resource usage metrics per resource kind:
- CPU usage percentage
- Memory usage (RSS)
- Event loop latency
- HTTP response body sizes

All metrics are tracked in memory only for statistics calculation.
"""

import asyncio
import statistics
import time
from dataclasses import asdict
from typing import Any, Optional

import psutil
from loguru import logger

from port_ocean.helpers.monitor.utils import measure_event_loop_latency

from .models import ProcessNode, SystemSnapshot, ResourceUsageStats


class PerformanceMonitor:
    """
    Collects performance metrics for Ocean per resource kind.

    Tracks:
    - CPU usage percentage (sampled in background)
    - Memory usage in bytes (sampled in background)
    - Event loop latency in ms (sampled in background)
    - HTTP response body sizes (recorded per request)

    All metrics are tracked in memory only for statistics calculation.
    """

    def __init__(self, interval: float = 0.5):
        self.interval = interval
        self._running = False
        self._task: Optional[asyncio.Task[None]] = None
        self._process = psutil.Process()
        self._start_time = time.time()

        # Track known PIDs for CPU baseline (first cpu_percent() call returns 0)
        self._known_pids: set[int] = set()

        # Initialize CPU measurement (first call establishes baseline)
        self._init_cpu_baseline()

        # Per-kind resource tracking
        self._kind_tracking: dict[str, dict[str, Any]] = {}
        self._current_tracking_kind: Optional[str] = None

    def _init_cpu_baseline(self) -> None:
        """Initialize CPU measurement baseline for main process and all children."""
        self._process.cpu_percent()
        self._known_pids.add(self._process.pid)
        for child in self._process.children(recursive=True):
            try:
                child.cpu_percent()
                self._known_pids.add(child.pid)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

    def _build_process_node(self, proc: psutil.Process) -> Optional[ProcessNode]:
        """
        Build a process tree node recursively.

        Returns a ProcessNode with all its children nested.

        Note: psutil.cpu_percent() returns 0 on the first call (needs a baseline).
        We track known PIDs to handle this - new PIDs get their baseline established
        but report 0 for this sample; subsequent samples will have real values.
        """
        try:
            pid = proc.pid
            mem = proc.memory_info()

            # Handle CPU measurement baseline issue
            # First call to cpu_percent() always returns 0 (establishes baseline)
            if pid in self._known_pids:
                cpu = proc.cpu_percent()
            else:
                # New PID - establish baseline, but use 0 for this sample
                proc.cpu_percent()  # Establish baseline
                self._known_pids.add(pid)
                cpu = 0.0  # Will get real value in next sample

            # Recursively build children (direct children only, they build their own)
            children = []
            for child in proc.children(recursive=False):
                child_node = self._build_process_node(child)
                if child_node:
                    children.append(asdict(child_node))

            return ProcessNode(
                cpu_percent=cpu,
                memory_rss=mem.rss,
                children=children,
            )
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None

    def _collect_process_tree(self) -> Optional[ProcessNode]:
        """
        Collect the full process tree starting from the main process.

        Returns a ProcessNode representing the main process with all
        descendant processes nested in a true tree structure.
        """
        return self._build_process_node(self._process)

    def _get_total_memory_rss(self) -> int:
        """
        Get total RSS memory usage including all child processes.
        """
        total_rss = self._process.memory_info().rss

        for child in self._process.children(recursive=True):
            try:
                total_rss += child.memory_info().rss
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        return total_rss

    # -------------------------------------------------------------------------
    # System Metrics (Background Sampling)
    # -------------------------------------------------------------------------

    async def _collect_system(self) -> SystemSnapshot:
        """Collect current system metrics: CPU, memory, and event loop latency."""
        # Measure event loop latency first (most accurate when done immediately)
        latency = await measure_event_loop_latency()

        # Get hierarchical process metrics (main + workers aggregated)
        process_tree = self._collect_process_tree()

        # Calculate totals from process tree (recursive sum)
        def sum_tree(node: ProcessNode) -> tuple[float, int]:
            """Sum cpu and memory from a tree node recursively."""
            cpu = node.cpu_percent
            mem = node.memory_rss
            for child_dict in node.children:
                child_cpu = child_dict.get("cpu_percent", 0)
                child_mem = child_dict.get("memory_rss", 0)
                cpu += child_cpu
                mem += child_mem
                # Recurse into grandchildren
                for grandchild in child_dict.get("children", []):
                    cpu += grandchild.get("cpu_percent", 0)
                    mem += grandchild.get("memory_rss", 0)
            return cpu, mem

        if process_tree:
            total_cpu, total_rss = sum_tree(process_tree)
        else:
            total_cpu = self._process.cpu_percent()
            total_rss = self._process.memory_info().rss

        return SystemSnapshot(
            process_cpu_percent=total_cpu,
            process_memory_rss=total_rss,
            event_loop_latency_ms=latency,
        )

    async def _sample_loop(self) -> None:
        """Background loop - samples system metrics every second."""
        while self._running:
            try:
                snapshot = await self._collect_system()

                # Store sample for current tracking kind if active
                if (
                    self._current_tracking_kind
                    and self._current_tracking_kind in self._kind_tracking
                ):
                    tracking = self._kind_tracking[self._current_tracking_kind]
                    tracking["cpu_samples"].append(snapshot.process_cpu_percent)
                    tracking["memory_samples"].append(snapshot.process_memory_rss)
                    tracking["latency_samples"].append(snapshot.event_loop_latency_ms)

            except Exception as e:
                logger.debug(f"Monitor error: {e}")
            await asyncio.sleep(self.interval)

    # -------------------------------------------------------------------------
    # Per-Kind Resource Tracking
    # -------------------------------------------------------------------------

    def start_kind_tracking(self, kind: str) -> None:
        """Start tracking resource usage for a specific kind.

        Args:
            kind: The resource kind identifier (e.g., "deployment-0")
        """
        self._kind_tracking[kind] = {
            "start_time": time.time(),
            "cpu_samples": [],
            "memory_samples": [],
            "latency_samples": [],
            "response_sizes": [],
        }
        self._current_tracking_kind = kind
        logger.info(f"[Monitor] Started tracking kind: {kind} (monitor_id={id(self)})")

    def stop_kind_tracking(self, kind: str) -> None:
        """Stop tracking resource usage for a specific kind.

        Args:
            kind: The resource kind identifier
        """
        if self._current_tracking_kind == kind:
            self._current_tracking_kind = None
        logger.debug(f"[Monitor] Stopped tracking kind: {kind}")

    @property
    def current_tracking_kind(self) -> Optional[str]:
        """Get the currently tracked kind, if any."""
        return self._current_tracking_kind

    def record_response_size(self, size_bytes: int) -> None:
        """Record the size of an HTTP response for the current tracking kind.

        Args:
            size_bytes: Size of the HTTP response in bytes
        """
        if (
            self._current_tracking_kind
            and self._current_tracking_kind in self._kind_tracking
        ):
            logger.info(
                f"[Monitor] Recorded response size: {size_bytes} bytes for kind: {self._current_tracking_kind} (monitor_id={id(self)})"
            )
            self._kind_tracking[self._current_tracking_kind]["response_sizes"].append(
                size_bytes
            )
        else:
            logger.info(
                f"[Monitor] Cannot record response size: {size_bytes} bytes - current_kind={self._current_tracking_kind}, tracking_kinds={list(self._kind_tracking.keys())} (monitor_id={id(self)})"
            )

    def get_kind_stats(self, kind: str) -> ResourceUsageStats:
        """Get resource usage statistics for a tracked kind.

        Calculates max, median, and average for CPU, memory, and latency
        from samples collected during kind processing.

        Args:
            kind: The resource kind identifier

        Returns:
            ResourceUsageStats with calculated statistics
        """
        if kind not in self._kind_tracking:
            logger.warning(f"[Monitor] No tracking data for kind: {kind}")
            return ResourceUsageStats()

        tracking = self._kind_tracking[kind]
        cpu_samples = tracking["cpu_samples"]
        memory_samples = tracking["memory_samples"]
        latency_samples = tracking["latency_samples"]
        response_sizes = tracking.get("response_sizes", [])

        if not cpu_samples:
            logger.debug(f"[Monitor] No samples collected for kind: {kind}")
            return ResourceUsageStats()

        # Calculate response size statistics
        response_size_total = sum(response_sizes) if response_sizes else 0
        response_size_avg = statistics.mean(response_sizes) if response_sizes else 0.0
        response_size_median = (
            statistics.median(response_sizes) if response_sizes else 0.0
        )

        stats = ResourceUsageStats(
            cpu_max=max(cpu_samples),
            cpu_median=statistics.median(cpu_samples),
            cpu_avg=statistics.mean(cpu_samples),
            memory_max=max(memory_samples),
            memory_median=int(statistics.median(memory_samples)),
            memory_avg=int(statistics.mean(memory_samples)),
            latency_max=max(latency_samples),
            latency_median=statistics.median(latency_samples),
            latency_avg=statistics.mean(latency_samples),
            response_size_total=response_size_total,
            response_size_avg=response_size_avg,
            response_size_median=response_size_median,
            request_count=len(response_sizes),
            sample_count=len(cpu_samples),
        )

        logger.debug(
            f"[Monitor] Stats for {kind}: CPU(max={stats.cpu_max:.1f}%, "
            f"med={stats.cpu_median:.1f}%, avg={stats.cpu_avg:.1f}%), "
            f"Mem(max={stats.memory_max / 1024**2:.1f}MB), "
            f"Latency(max={stats.latency_max:.2f}ms), "
            f"RequestSize(total={stats.response_size_total / 1024**2:.2f}MB, "
            f"avg={stats.response_size_avg / 1024:.1f}KB, med={stats.response_size_median / 1024:.1f}KB, "
            f"count={stats.request_count}), samples={stats.sample_count}"
        )

        return stats

    def cleanup_kind_tracking(self, kind: str) -> None:
        """Clean up tracking data for a kind after stats have been retrieved.

        Args:
            kind: The resource kind identifier
        """
        if kind in self._kind_tracking:
            del self._kind_tracking[kind]

    # -------------------------------------------------------------------------
    # Lifecycle
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """Start monitoring."""
        if self._running:
            return
        self._running = True
        self._start_time = time.time()

        self._task = asyncio.create_task(self._sample_loop())
        logger.info("[Monitor] Started")

    async def stop(self) -> dict[str, Any]:
        """Stop monitoring and return summary."""
        if not self._running:
            return {}
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        summary = {
            "duration_seconds": time.time() - self._start_time,
            "current_memory_mb": self._get_total_memory_rss() / (1024**2),
        }

        logger.info("[Monitor] Stopped")
        return summary


_monitor: Optional[PerformanceMonitor] = None


def get_monitor() -> PerformanceMonitor:
    """Get the global monitor instance, creating one if it doesn't exist."""
    global _monitor
    if _monitor is None:
        _monitor = PerformanceMonitor()
    return _monitor


async def start_monitoring() -> PerformanceMonitor:
    """Start monitoring. If a monitor is already running, return the existing one.

    This is idempotent - calling it multiple times won't create multiple monitors
    or reset the tracking state.
    """
    global _monitor
    # If monitor already exists and is running, return it (don't create a new one!)
    if _monitor is not None and _monitor._running:
        logger.debug(
            f"[Monitor] Already running, returning existing instance (monitor_id={id(_monitor)})"
        )
        return _monitor

    # Create new monitor only if none exists or previous one was stopped
    _monitor = PerformanceMonitor()
    await _monitor.start()
    return _monitor


async def stop_monitoring() -> dict[str, Any]:
    """Stop the global monitor and return summary."""
    global _monitor
    if _monitor:
        return await _monitor.stop()
    return {}
