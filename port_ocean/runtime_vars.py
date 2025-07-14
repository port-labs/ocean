import os

import psutil


def get_memory_limit_mb():
    # cgroup v2
    try:
        with open("/sys/fs/cgroup/memory.max") as f:
            limit = f.read().strip()
        if limit.isdigit():
            return int(limit) // (1024 * 1024)
        raise ValueError
    except Exception:
        # cgroup v1
        try:
            with open("/sys/fs/cgroup/memory/memory.limit_in_bytes") as f:
                return int(f.read()) // (1024 * 1024)
        except Exception:
            # fallback to host total RAM
            return psutil.virtual_memory().total // (1024 * 1024)


def estimate_worker_rss_mb():
    """Measure this process’s RSS once imports have settled."""
    rss_bytes = psutil.Process(os.getpid()).memory_info().rss
    return max(rss_bytes // (1024 * 1024), 50)  # floor at 50 MB


TOTAL_MEM_MB = get_memory_limit_mb()
PER_WORKER_MB = estimate_worker_rss_mb()
BY_MEM = max(1, TOTAL_MEM_MB // PER_WORKER_MB)
BY_CPU = os.cpu_count() or 1  # assuming virtual core num
workers = min(BY_MEM, BY_CPU)

mem_per_worker = TOTAL_MEM_MB / workers
max_requests = max(100, int(mem_per_worker))
