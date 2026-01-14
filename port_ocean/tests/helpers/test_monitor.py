"""Tests for the performance monitor module."""

import asyncio
from unittest.mock import Mock, patch, MagicMock
import pytest

from port_ocean.helpers.monitor.models import (
    ResourceUsageStats,
    ProcessNode,
    SystemSnapshot,
)
from port_ocean.helpers.monitor.monitor import (
    PerformanceMonitor,
    get_monitor,
    start_monitoring,
    stop_monitoring,
)
from port_ocean.helpers.monitor.utils import (
    is_container,
    _read_cgroup,
    measure_event_loop_latency,
)
from port_ocean.helpers.monitor.cgrouop_reader import CgroupReader
from port_ocean.helpers.metric.metric import MetricType, _metrics_registry
import port_ocean.helpers.monitor.monitor as monitor_module


class TestResourceUsageStats:
    """Tests for ResourceUsageStats dataclass."""

    def test_default_values(self) -> None:
        """Test that ResourceUsageStats has correct default values."""
        stats = ResourceUsageStats()

        assert stats.cpu_max == 0.0
        assert stats.cpu_median == 0.0
        assert stats.cpu_avg == 0.0
        assert stats.memory_max == 0
        assert stats.memory_median == 0
        assert stats.memory_avg == 0
        assert stats.latency_max == 0.0
        assert stats.latency_median == 0.0
        assert stats.latency_avg == 0.0
        assert stats.request_size_total == 0
        assert stats.request_size_avg == 0.0
        assert stats.request_size_median == 0.0
        assert stats.request_count == 0
        assert stats.sample_count == 0

    def test_custom_values(self) -> None:
        """Test ResourceUsageStats with custom values."""
        stats = ResourceUsageStats(
            cpu_max=100.0,
            cpu_median=50.0,
            cpu_avg=55.0,
            memory_max=1024 * 1024 * 100,  # 100MB
            memory_median=1024 * 1024 * 80,
            memory_avg=1024 * 1024 * 75,
            latency_max=10.5,
            latency_median=2.0,
            latency_avg=3.5,
            request_size_total=1024 * 1024,
            request_size_avg=1024.0,
            request_size_median=512.0,
            request_count=1000,
            sample_count=50,
        )

        assert stats.cpu_max == 100.0
        assert stats.memory_max == 1024 * 1024 * 100
        assert stats.request_count == 1000
        assert stats.sample_count == 50


class TestProcessNode:
    """Tests for ProcessNode dataclass."""

    def test_process_node_creation(self) -> None:
        """Test ProcessNode creation with valid data."""
        node = ProcessNode(
            cpu_percent=25.5,
            memory_rss=1024 * 1024 * 50,
            children=[],
        )

        assert node.cpu_percent == 25.5
        assert node.memory_rss == 1024 * 1024 * 50
        assert node.children == []

    def test_process_node_with_children(self) -> None:
        """Test ProcessNode with nested children."""
        child_data = {
            "cpu_percent": 10.0,
            "memory_rss": 1024 * 1024,
            "children": [],
        }
        node = ProcessNode(
            cpu_percent=25.5,
            memory_rss=1024 * 1024 * 50,
            children=[child_data],
        )

        assert len(node.children) == 1
        assert node.children[0]["cpu_percent"] == 10.0


class TestSystemSnapshot:
    """Tests for SystemSnapshot dataclass."""

    def test_system_snapshot_creation(self) -> None:
        """Test SystemSnapshot creation."""
        snapshot = SystemSnapshot(
            process_cpu_percent=45.5,
            process_memory_rss=1024 * 1024 * 100,
            event_loop_latency_ms=0.5,
        )

        assert snapshot.process_cpu_percent == 45.5
        assert snapshot.process_memory_rss == 1024 * 1024 * 100
        assert snapshot.event_loop_latency_ms == 0.5


class TestMonitorUtils:
    """Tests for monitor utility functions."""

    def test_is_container_no_dockerenv(self) -> None:
        """Test is_container returns False when not in container."""
        with patch("os.path.exists", return_value=False):
            with patch("builtins.open", side_effect=FileNotFoundError("No such file")):
                result = is_container()
                assert result is False

    def test_is_container_with_dockerenv(self) -> None:
        """Test is_container returns True when .dockerenv exists."""
        with patch("os.path.exists", return_value=True):
            result = is_container()
            assert result is True

    def test_is_container_with_cgroup_docker(self) -> None:
        """Test is_container detects Docker via cgroup."""
        with patch("os.path.exists", return_value=False):
            mock_file = MagicMock()
            mock_file.__enter__ = Mock(return_value=mock_file)
            mock_file.__exit__ = Mock(return_value=False)
            mock_file.read.return_value = "12:devices:/docker/abc123"

            with patch("builtins.open", return_value=mock_file):
                result = is_container()
                assert result is True

    def test_read_cgroup_success(self) -> None:
        """Test _read_cgroup reads integer value."""
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.read.return_value = "1073741824\n"

        with patch("builtins.open", return_value=mock_file):
            result = _read_cgroup("/sys/fs/cgroup/memory.max")
            assert result == 1073741824

    def test_read_cgroup_max_value(self) -> None:
        """Test _read_cgroup returns None for 'max' value."""
        mock_file = MagicMock()
        mock_file.__enter__ = Mock(return_value=mock_file)
        mock_file.__exit__ = Mock(return_value=False)
        mock_file.read.return_value = "max\n"

        with patch("builtins.open", return_value=mock_file):
            result = _read_cgroup("/sys/fs/cgroup/memory.max")
            assert result is None

    def test_read_cgroup_file_not_found(self) -> None:
        """Test _read_cgroup returns None on file not found."""
        with patch("builtins.open", side_effect=FileNotFoundError()):
            result = _read_cgroup("/nonexistent/path")
            assert result is None

    @pytest.mark.asyncio
    async def test_measure_event_loop_latency(self) -> None:
        """Test measure_event_loop_latency returns a positive value."""
        latency = await measure_event_loop_latency()

        assert isinstance(latency, float)
        assert latency >= 0.0


class TestCgroupReader:
    """Tests for CgroupReader class."""

    def test_cgroup_reader_init_not_container(self) -> None:
        """Test CgroupReader initialization when not in container."""
        with patch(
            "port_ocean.helpers.monitor.cgrouop_reader.is_container", return_value=False
        ):
            with patch("os.path.exists", return_value=False):
                reader = CgroupReader()

                assert reader.is_container is False
                assert reader._prev_cpu_usage is None
                assert reader._prev_cpu_time is None

    def test_memory_limit_not_container(self) -> None:
        """Test memory_limit returns None when not in container."""
        with patch(
            "port_ocean.helpers.monitor.cgrouop_reader.is_container", return_value=False
        ):
            with patch("os.path.exists", return_value=False):
                reader = CgroupReader()
                result = reader.memory_limit()

                assert result is None

    def test_memory_usage_not_container(self) -> None:
        """Test memory_usage returns None when not in container."""
        with patch(
            "port_ocean.helpers.monitor.cgrouop_reader.is_container", return_value=False
        ):
            with patch("os.path.exists", return_value=False):
                reader = CgroupReader()
                result = reader.memory_usage()

                assert result is None

    def test_cpu_percent_not_container(self) -> None:
        """Test cpu_percent returns 0.0 when not in container."""
        with patch(
            "port_ocean.helpers.monitor.cgrouop_reader.is_container", return_value=False
        ):
            with patch("os.path.exists", return_value=False):
                reader = CgroupReader()
                result = reader.cpu_percent()

                assert result == 0.0


class TestPerformanceMonitor:
    """Tests for PerformanceMonitor class."""

    @pytest.fixture
    def monitor(self) -> PerformanceMonitor:
        """Create a fresh monitor instance for each test."""
        return PerformanceMonitor(interval=0.1)

    def test_monitor_initialization(self, monitor: PerformanceMonitor) -> None:
        """Test monitor initializes with correct defaults."""
        assert monitor.interval == 0.1
        assert monitor._running is False
        assert monitor._task is None
        assert monitor._kind_tracking == {}
        assert monitor._current_tracking_kind is None

    def test_start_kind_tracking(self, monitor: PerformanceMonitor) -> None:
        """Test starting kind tracking."""
        monitor.start_kind_tracking("test-kind-0")

        assert "test-kind-0" in monitor._kind_tracking
        assert monitor._current_tracking_kind == "test-kind-0"
        tracking = monitor._kind_tracking["test-kind-0"]
        assert "start_time" in tracking
        assert tracking["cpu_samples"] == []
        assert tracking["memory_samples"] == []
        assert tracking["latency_samples"] == []
        assert tracking["request_sizes"] == []

    def test_stop_kind_tracking(self, monitor: PerformanceMonitor) -> None:
        """Test stopping kind tracking."""
        monitor.start_kind_tracking("test-kind-0")
        monitor.stop_kind_tracking("test-kind-0")

        assert monitor._current_tracking_kind is None
        # Data should still be available until cleanup
        assert "test-kind-0" in monitor._kind_tracking

    def test_current_tracking_kind_property(self, monitor: PerformanceMonitor) -> None:
        """Test current_tracking_kind property."""
        assert monitor.current_tracking_kind is None

        monitor.start_kind_tracking("test-kind")
        assert monitor.current_tracking_kind == "test-kind"

        monitor.stop_kind_tracking("test-kind")
        assert monitor.current_tracking_kind is None

    def test_record_request_size(self, monitor: PerformanceMonitor) -> None:
        """Test recording request size."""
        monitor.start_kind_tracking("test-kind-0")
        monitor.record_request_size(1024)
        monitor.record_request_size(2048)

        tracking = monitor._kind_tracking["test-kind-0"]
        assert tracking["request_sizes"] == [1024, 2048]

    def test_record_request_size_no_active_kind(
        self, monitor: PerformanceMonitor
    ) -> None:
        """Test recording request size with no active tracking."""
        # Should not raise, just log
        monitor.record_request_size(1024)

    def test_cleanup_kind_tracking(self, monitor: PerformanceMonitor) -> None:
        """Test cleaning up tracking data."""
        monitor.start_kind_tracking("test-kind-0")
        monitor.cleanup_kind_tracking("test-kind-0")

        assert "test-kind-0" not in monitor._kind_tracking

    def test_get_kind_stats_empty(self, monitor: PerformanceMonitor) -> None:
        """Test getting stats for non-existent kind."""
        stats = monitor.get_kind_stats("nonexistent")

        assert stats.sample_count == 0
        assert stats.cpu_max == 0.0

    def test_get_kind_stats_no_samples(self, monitor: PerformanceMonitor) -> None:
        """Test getting stats when no samples collected."""
        monitor.start_kind_tracking("test-kind-0")
        stats = monitor.get_kind_stats("test-kind-0")

        assert stats.sample_count == 0

    def test_get_kind_stats_with_samples(self, monitor: PerformanceMonitor) -> None:
        """Test getting stats with sample data."""
        monitor.start_kind_tracking("test-kind-0")

        # Manually add samples
        tracking = monitor._kind_tracking["test-kind-0"]
        tracking["cpu_samples"] = [10.0, 20.0, 30.0, 40.0, 50.0]
        tracking["memory_samples"] = [100, 200, 300, 400, 500]
        tracking["latency_samples"] = [1.0, 2.0, 3.0, 4.0, 5.0]
        tracking["request_sizes"] = [1000, 2000, 3000]

        stats = monitor.get_kind_stats("test-kind-0")

        assert stats.cpu_max == 50.0
        assert stats.cpu_median == 30.0
        assert stats.cpu_avg == 30.0
        assert stats.memory_max == 500
        assert stats.memory_median == 300
        assert stats.memory_avg == 300
        assert stats.latency_max == 5.0
        assert stats.latency_median == 3.0
        assert stats.latency_avg == 3.0
        assert stats.request_size_total == 6000
        assert stats.request_size_avg == 2000.0
        assert stats.request_size_median == 2000.0
        assert stats.request_count == 3
        assert stats.sample_count == 5

    def test_get_total_memory_rss(self, monitor: PerformanceMonitor) -> None:
        """Test getting total memory RSS."""
        memory = monitor._get_total_memory_rss()

        assert isinstance(memory, int)
        assert memory > 0

    @pytest.mark.asyncio
    async def test_start_and_stop(self, monitor: PerformanceMonitor) -> None:
        """Test starting and stopping the monitor."""
        await monitor.start()

        assert monitor._running is True
        assert monitor._task is not None

        summary = await monitor.stop()

        assert monitor._running is False
        assert "duration_seconds" in summary
        assert "current_memory_mb" in summary
        assert summary["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_start_idempotent(self, monitor: PerformanceMonitor) -> None:
        """Test that start is idempotent."""
        await monitor.start()
        task1 = monitor._task

        await monitor.start()  # Should be no-op
        task2 = monitor._task

        assert task1 is task2

        await monitor.stop()

    @pytest.mark.asyncio
    async def test_stop_when_not_running(self, monitor: PerformanceMonitor) -> None:
        """Test stopping when not running returns empty dict."""
        summary = await monitor.stop()

        assert summary == {}

    @pytest.mark.asyncio
    async def test_collect_system(self, monitor: PerformanceMonitor) -> None:
        """Test collecting system metrics."""
        snapshot = await monitor._collect_system()

        assert isinstance(snapshot, SystemSnapshot)
        assert isinstance(snapshot.process_cpu_percent, float)
        assert isinstance(snapshot.process_memory_rss, int)
        assert isinstance(snapshot.event_loop_latency_ms, float)
        assert snapshot.process_memory_rss > 0

    @pytest.mark.asyncio
    async def test_sample_loop_stores_samples(
        self, monitor: PerformanceMonitor
    ) -> None:
        """Test that sample loop stores samples for tracked kind."""
        monitor.start_kind_tracking("test-kind-0")
        await monitor.start()

        # Let it run for a bit
        await asyncio.sleep(0.3)

        await monitor.stop()

        tracking = monitor._kind_tracking["test-kind-0"]
        # Should have collected at least one sample
        assert len(tracking["cpu_samples"]) > 0
        assert len(tracking["memory_samples"]) > 0
        assert len(tracking["latency_samples"]) > 0


class TestGlobalMonitorFunctions:
    """Tests for global monitor functions."""

    @pytest.fixture(autouse=True)
    def reset_global_monitor(self) -> None:
        """Reset the global monitor before each test."""
        monitor_module._monitor = None

    def test_get_monitor_creates_instance(self) -> None:
        """Test get_monitor creates a new instance if none exists."""
        monitor = get_monitor()

        assert isinstance(monitor, PerformanceMonitor)

    def test_get_monitor_returns_same_instance(self) -> None:
        """Test get_monitor returns the same instance on subsequent calls."""
        monitor1 = get_monitor()
        monitor2 = get_monitor()

        assert monitor1 is monitor2

    @pytest.mark.asyncio
    async def test_start_monitoring(self) -> None:
        """Test start_monitoring function."""
        monitor = await start_monitoring()

        assert isinstance(monitor, PerformanceMonitor)
        assert monitor._running is True

        await stop_monitoring()

    @pytest.mark.asyncio
    async def test_start_monitoring_idempotent(self) -> None:
        """Test start_monitoring is idempotent."""
        monitor1 = await start_monitoring()
        monitor2 = await start_monitoring()

        assert monitor1 is monitor2

        await stop_monitoring()

    @pytest.mark.asyncio
    async def test_stop_monitoring(self) -> None:
        """Test stop_monitoring function."""
        await start_monitoring()
        summary = await stop_monitoring()

        assert "duration_seconds" in summary
        assert "current_memory_mb" in summary

    @pytest.mark.asyncio
    async def test_stop_monitoring_when_not_started(self) -> None:
        """Test stop_monitoring when no monitor exists."""
        summary = await stop_monitoring()

        assert summary == {}


class TestProcessTreeBuilding:
    """Tests for process tree building functionality."""

    @pytest.fixture
    def monitor(self) -> PerformanceMonitor:
        """Create a fresh monitor instance."""
        return PerformanceMonitor(interval=0.1)

    def test_build_process_node(self, monitor: PerformanceMonitor) -> None:
        """Test building a process node."""
        node = monitor._build_process_node(monitor._process)

        assert node is not None
        assert isinstance(node.cpu_percent, float)
        assert isinstance(node.memory_rss, int)
        assert isinstance(node.children, list)
        assert node.memory_rss > 0

    def test_collect_process_tree(self, monitor: PerformanceMonitor) -> None:
        """Test collecting the process tree."""
        tree = monitor._collect_process_tree()

        assert tree is not None
        assert isinstance(tree, ProcessNode)

    def test_init_cpu_baseline(self, monitor: PerformanceMonitor) -> None:
        """Test CPU baseline initialization."""
        # After init, the main process PID should be in known_pids
        assert monitor._process.pid in monitor._known_pids


class TestMetricTypeConstants:
    """Tests for new MetricType constants added for monitor metrics."""

    def test_cpu_metric_types_exist(self) -> None:
        """Test that CPU metric type constants are defined."""
        assert hasattr(MetricType, "CPU_MAX_NAME")
        assert hasattr(MetricType, "CPU_MEDIAN_NAME")
        assert hasattr(MetricType, "CPU_AVG_NAME")

        assert MetricType.CPU_MAX_NAME == "cpu_max_percent"
        assert MetricType.CPU_MEDIAN_NAME == "cpu_median_percent"
        assert MetricType.CPU_AVG_NAME == "cpu_avg_percent"

    def test_memory_metric_types_exist(self) -> None:
        """Test that memory metric type constants are defined."""
        assert hasattr(MetricType, "MEMORY_MAX_NAME")
        assert hasattr(MetricType, "MEMORY_MEDIAN_NAME")
        assert hasattr(MetricType, "MEMORY_AVG_NAME")

        assert MetricType.MEMORY_MAX_NAME == "memory_max_bytes"
        assert MetricType.MEMORY_MEDIAN_NAME == "memory_median_bytes"
        assert MetricType.MEMORY_AVG_NAME == "memory_avg_bytes"

    def test_latency_metric_types_exist(self) -> None:
        """Test that latency metric type constants are defined."""
        assert hasattr(MetricType, "LATENCY_MAX_NAME")
        assert hasattr(MetricType, "LATENCY_MEDIAN_NAME")
        assert hasattr(MetricType, "LATENCY_AVG_NAME")

        assert MetricType.LATENCY_MAX_NAME == "event_loop_latency_max_ms"
        assert MetricType.LATENCY_MEDIAN_NAME == "event_loop_latency_median_ms"
        assert MetricType.LATENCY_AVG_NAME == "event_loop_latency_avg_ms"

    def test_request_size_metric_types_exist(self) -> None:
        """Test that request size metric type constants are defined."""
        assert hasattr(MetricType, "REQUEST_SIZE_TOTAL_NAME")
        assert hasattr(MetricType, "REQUEST_SIZE_AVG_NAME")
        assert hasattr(MetricType, "REQUEST_SIZE_MEDIAN_NAME")

        assert MetricType.REQUEST_SIZE_TOTAL_NAME == "request_size_total_bytes"
        assert MetricType.REQUEST_SIZE_AVG_NAME == "request_size_avg_bytes"
        assert MetricType.REQUEST_SIZE_MEDIAN_NAME == "request_size_median_bytes"

    def test_cpu_metrics_registered(self) -> None:
        """Test that CPU metrics are registered in the metrics registry."""
        assert MetricType.CPU_MAX_NAME in _metrics_registry
        assert MetricType.CPU_MEDIAN_NAME in _metrics_registry
        assert MetricType.CPU_AVG_NAME in _metrics_registry

        # Check registry entry format: (name, description, labels)
        cpu_max_entry = _metrics_registry[MetricType.CPU_MAX_NAME]
        assert len(cpu_max_entry) == 3
        assert cpu_max_entry[0] == MetricType.CPU_MAX_NAME
        assert "CPU" in cpu_max_entry[1] or "cpu" in cpu_max_entry[1].lower()
        assert "kind" in cpu_max_entry[2]

    def test_memory_metrics_registered(self) -> None:
        """Test that memory metrics are registered in the metrics registry."""
        assert MetricType.MEMORY_MAX_NAME in _metrics_registry
        assert MetricType.MEMORY_MEDIAN_NAME in _metrics_registry
        assert MetricType.MEMORY_AVG_NAME in _metrics_registry

    def test_latency_metrics_registered(self) -> None:
        """Test that latency metrics are registered in the metrics registry."""
        assert MetricType.LATENCY_MAX_NAME in _metrics_registry
        assert MetricType.LATENCY_MEDIAN_NAME in _metrics_registry
        assert MetricType.LATENCY_AVG_NAME in _metrics_registry

    def test_request_size_metrics_registered(self) -> None:
        """Test that request size metrics are registered in the metrics registry."""
        assert MetricType.REQUEST_SIZE_TOTAL_NAME in _metrics_registry
        assert MetricType.REQUEST_SIZE_AVG_NAME in _metrics_registry
        assert MetricType.REQUEST_SIZE_MEDIAN_NAME in _metrics_registry


class TestMonitorIntegration:
    """Integration tests for the monitor."""

    @pytest.mark.asyncio
    async def test_full_tracking_workflow(self) -> None:
        """Test complete workflow: start, track, collect stats, cleanup."""
        monitor = PerformanceMonitor(interval=0.1)

        # Start monitoring
        await monitor.start()

        # Start tracking a kind
        monitor.start_kind_tracking("deployment-0")

        # Record some request sizes
        monitor.record_request_size(1024)
        monitor.record_request_size(2048)
        monitor.record_request_size(4096)

        # Let some samples be collected
        await asyncio.sleep(0.25)

        # Stop tracking
        monitor.stop_kind_tracking("deployment-0")

        # Get stats
        stats = monitor.get_kind_stats("deployment-0")

        # Verify stats
        assert stats.sample_count > 0
        assert stats.request_count == 3
        assert stats.request_size_total == 7168
        assert stats.cpu_max >= 0
        assert stats.memory_max > 0

        # Cleanup
        monitor.cleanup_kind_tracking("deployment-0")
        assert "deployment-0" not in monitor._kind_tracking

        # Stop monitoring
        await monitor.stop()

    @pytest.mark.asyncio
    async def test_multiple_kinds_tracking(self) -> None:
        """Test tracking multiple kinds sequentially."""
        monitor = PerformanceMonitor(interval=0.1)
        await monitor.start()

        # Track first kind
        monitor.start_kind_tracking("kind-0")
        monitor.record_request_size(1000)
        await asyncio.sleep(0.15)
        monitor.stop_kind_tracking("kind-0")

        # Track second kind
        monitor.start_kind_tracking("kind-1")
        monitor.record_request_size(2000)
        await asyncio.sleep(0.15)
        monitor.stop_kind_tracking("kind-1")

        # Get stats for both
        stats0 = monitor.get_kind_stats("kind-0")
        stats1 = monitor.get_kind_stats("kind-1")

        assert stats0.request_size_total == 1000
        assert stats1.request_size_total == 2000

        await monitor.stop()
