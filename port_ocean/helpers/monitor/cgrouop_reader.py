from typing import Optional
import os
from port_ocean.helpers.monitor.utils import is_container, _read_cgroup
import time
import psutil


class CgroupReader:
    """Reads container limits from cgroups (v1 and v2)."""

    def __init__(self) -> None:
        self.v2 = os.path.exists("/sys/fs/cgroup/cgroup.controllers")
        self.is_container = is_container()
        self._prev_cpu_usage: Optional[int] = None
        self._prev_cpu_time: Optional[float] = None

    def memory_limit(self) -> Optional[int]:
        if not self.is_container:
            return None
        if self.v2:
            return _read_cgroup("/sys/fs/cgroup/memory.max")
        return _read_cgroup("/sys/fs/cgroup/memory/memory.limit_in_bytes")

    def memory_usage(self) -> Optional[int]:
        if not self.is_container:
            return None
        if self.v2:
            return _read_cgroup("/sys/fs/cgroup/memory.current")
        return _read_cgroup("/sys/fs/cgroup/memory/memory.usage_in_bytes")

    def cpu_limit_cores(self) -> Optional[float]:
        """Get CPU limit in number of cores (e.g., 0.5 = half a core, 2.0 = 2 cores)."""
        if not self.is_container:
            return None
        if self.v2:
            # cgroup v2: cpu.max contains "quota period" or "max period"
            try:
                with open("/sys/fs/cgroup/cpu.max", "r") as f:
                    parts = f.read().strip().split()
                    if parts[0] == "max":
                        return None  # unlimited
                    quota = int(parts[0])
                    period = int(parts[1]) if len(parts) > 1 else 100000
                    return quota / period
            except (FileNotFoundError, PermissionError, ValueError, IndexError):
                return None
        else:
            # cgroup v1
            quota = _read_cgroup("/sys/fs/cgroup/cpu/cpu.cfs_quota_us") or 0
            period = _read_cgroup("/sys/fs/cgroup/cpu/cpu.cfs_period_us") or 0
            if quota and period and quota > 0:
                return quota / period
            return None

    def cpu_usage_ns(self) -> Optional[int]:
        """Get total CPU usage in nanoseconds."""
        if not self.is_container:
            return None
        if self.v2:
            # cgroup v2: cpu.stat contains usage_usec
            try:
                with open("/sys/fs/cgroup/cpu.stat", "r") as f:
                    for line in f:
                        if line.startswith("usage_usec"):
                            return int(line.split()[1]) * 1000  # convert to ns
            except (FileNotFoundError, PermissionError, ValueError):
                return None
        else:
            # cgroup v1: cpuacct.usage is in nanoseconds
            return _read_cgroup("/sys/fs/cgroup/cpuacct/cpuacct.usage")
        return None

    def cpu_percent(self) -> float:
        """
        Calculate CPU usage percentage relative to container limit.
        Returns percentage where 100% = using all allocated CPU.
        """
        if not self.is_container:
            return 0.0

        current_usage = self.cpu_usage_ns()
        current_time = time.time()

        if current_usage is None:
            return 0.0

        # Need previous measurement to calculate delta
        if self._prev_cpu_usage is None or self._prev_cpu_time is None:
            self._prev_cpu_usage = current_usage
            self._prev_cpu_time = current_time
            return 0.0

        # Calculate CPU percentage
        usage_delta = current_usage - self._prev_cpu_usage
        time_delta = current_time - self._prev_cpu_time

        self._prev_cpu_usage = current_usage
        self._prev_cpu_time = current_time

        if time_delta <= 0:
            return 0.0

        # usage_delta is in nanoseconds, time_delta is in seconds
        # CPU usage per second in nanoseconds / 1e9 = fraction of one core
        cpu_cores_used = (usage_delta / 1e9) / time_delta

        # Get limit (in cores)
        limit = self.cpu_limit_cores()
        if limit:
            # Percentage relative to container limit
            return (cpu_cores_used / limit) * 100
        else:
            # No limit - use number of host CPUs
            return (cpu_cores_used / (psutil.cpu_count() or 1)) * 100
