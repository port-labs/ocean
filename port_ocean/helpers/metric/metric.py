from typing import Any, TYPE_CHECKING, Optional, Dict, List, Tuple
from fastapi import APIRouter
from port_ocean.exceptions.context import ResourceContextNotFoundError
import prometheus_client
from httpx import AsyncClient

from loguru import logger
from port_ocean.context import resource
from prometheus_client import Gauge
import prometheus_client.openmetrics
import prometheus_client.openmetrics.exposition
import prometheus_client.parser

if TYPE_CHECKING:
    from port_ocean.config.settings import MetricsSettings, IntegrationSettings


class MetricPhase:
    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"
    RESYNC = "resync"
    DELETE = "delete"

    class TransformResult:
        TRANSFORMED = "transformed"
        FILTERED_OUT = "filtered_out"
        FAILED = "failed"

    class LoadResult:
        LOADED = "loaded"
        FAILED = "failed"
        SKIPPED = "skipped"

    class ExtractResult:
        EXTRACTED = "raw_extracted"


class MetricType:
    # Define metric names as constants
    DURATION_NAME = "duration_seconds"
    OBJECT_COUNT_NAME = "object_count"
    ERROR_COUNT_NAME = "error_count"
    SUCCESS_NAME = "success"
    RATE_LIMIT_WAIT_NAME = "rate_limit_wait_seconds"
    DELETION_COUNT_NAME = "deletion_count"


class SyncState:
    SYNCING = "syncing"
    COMPLETED = "completed"
    QUEUED = "queued"
    FAILED = "failed"


# Registry for core and custom metrics
_metrics_registry: Dict[str, Tuple[str, str, List[str]]] = {
    MetricType.DURATION_NAME: (
        MetricType.DURATION_NAME,
        "duration description",
        ["kind", "phase"],
    ),
    MetricType.OBJECT_COUNT_NAME: (
        MetricType.OBJECT_COUNT_NAME,
        "object_count description",
        ["kind", "phase", "object_count_type"],
    ),
    MetricType.ERROR_COUNT_NAME: (
        MetricType.ERROR_COUNT_NAME,
        "error_count description",
        ["kind", "phase"],
    ),
    MetricType.SUCCESS_NAME: (
        MetricType.SUCCESS_NAME,
        "success description",
        ["kind", "phase"],
    ),
    MetricType.RATE_LIMIT_WAIT_NAME: (
        MetricType.RATE_LIMIT_WAIT_NAME,
        "rate_limit_wait description",
        ["kind", "phase", "endpoint"],
    ),
    MetricType.DELETION_COUNT_NAME: (
        MetricType.DELETION_COUNT_NAME,
        "deletion_count description",
        ["kind", "phase"],
    ),
}


def register_metric(name: str, description: str, labels: List[str]) -> None:
    """Register a custom metric that will be available for use.

    Args:
        name (str): The metric name to register
        description (str): Description of what the metric measures
        labels (list[str]): Labels to apply to the metric
    """
    _metrics_registry[name] = (name, description, labels)


class EmptyMetric:
    def set(self, *args: Any) -> None:
        return None

    def labels(self, *args: Any) -> None:
        return None

    def inc(self, *args: Any) -> None:
        return None


class Metrics:
    def __init__(
        self,
        metrics_settings: "MetricsSettings",
        integration_configuration: "IntegrationSettings",
    ) -> None:
        self.metrics_settings = metrics_settings
        self.integration_configuration = integration_configuration
        self.registry = prometheus_client.CollectorRegistry()
        self.metrics: dict[str, Gauge] = {}
        self.load_metrics()
        self._integration_version: Optional[str] = None
        self._ocean_version: Optional[str] = None
        self.event_id = ""
        self.sync_state = SyncState.QUEUED

    @property
    def event_id(self) -> str:
        return self._event_id

    @event_id.setter
    def event_id(self, value: str) -> None:
        self._event_id = value

    @property
    def sync_state(self) -> str:
        return self._sync_state

    @sync_state.setter
    def sync_state(self, value: str) -> None:
        self._sync_state = value

    @property
    def integration_version(self) -> str:
        if self._integration_version is None:
            from port_ocean.version import __integration_version__

            self._integration_version = __integration_version__
        return self._integration_version

    @property
    def ocean_version(self) -> str:
        if self._ocean_version is None:
            from port_ocean.version import __version__

            self._ocean_version = __version__
        return self._ocean_version

    @property
    def enabled(self) -> bool:
        return self.metrics_settings.enabled

    def load_metrics(self) -> None:
        if not self.enabled:
            return None

        # Load all registered metrics
        for name, (_, description, labels) in _metrics_registry.items():
            self.metrics[name] = Gauge(
                name, description, labels, registry=self.registry
            )

    def get_metric(self, name: str, labels: list[str]) -> Gauge | EmptyMetric:
        if not self.enabled:
            return EmptyMetric()
        metrics = self.metrics.get(name)
        if not metrics:
            return EmptyMetric()
        return metrics.labels(*labels)

    def inc_metric(self, name: str, labels: list[str], value: float) -> None:
        """Increment a metric value in a single method call.

        Args:
            name (str): The metric name to inc.
            labels (list[str]): The labels to apply to the metric.
            value (float): The value to inc.
        """
        if not self.enabled:
            return None

        self.get_metric(name, labels).inc(value)

    def set_metric(self, name: str, labels: list[str], value: float) -> None:
        """Set a metric value in a single method call.

        Args:
            name (str): The metric name to set.
            labels (list[str]): The labels to apply to the metric.
            value (float): The value to set.
        """
        if not self.enabled:
            return None

        self.get_metric(name, labels).set(value)

    def initialize_metrics(self, kind_blockes: list[str]) -> None:
        for kind in kind_blockes:
            self.set_metric(MetricType.SUCCESS_NAME, [kind, MetricPhase.RESYNC], 0)
            self.set_metric(MetricType.DURATION_NAME, [kind, MetricPhase.RESYNC], 0)

            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.EXTRACT, MetricPhase.ExtractResult.EXTRACTED],
                0,
            )

            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.TRANSFORM, MetricPhase.TransformResult.TRANSFORMED],
                0,
            )
            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.TRANSFORM, MetricPhase.TransformResult.FILTERED_OUT],
                0,
            )
            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.TRANSFORM, MetricPhase.TransformResult.FAILED],
                0,
            )

            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.LOAD, MetricPhase.LoadResult.LOADED],
                0,
            )
            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.LOAD, MetricPhase.LoadResult.FAILED],
                0,
            )
            self.set_metric(
                MetricType.OBJECT_COUNT_NAME,
                [kind, MetricPhase.LOAD, MetricPhase.LoadResult.SKIPPED],
                0,
            )

    def create_mertic_router(self) -> APIRouter:
        if not self.enabled:
            return APIRouter()
        router = APIRouter()

        @router.get("/")
        async def prom_metrics() -> str:
            return self.generate_latest()

        return router

    def current_resource_kind(self) -> str:
        try:
            return f"{resource.resource.kind}-{resource.resource.index}"
        except ResourceContextNotFoundError:
            return "__runtime__"

    def generate_latest(self) -> str:
        return prometheus_client.openmetrics.exposition.generate_latest(
            self.registry
        ).decode()

    async def flush(
        self, metric_name: Optional[str] = None, kind: Optional[str] = None
    ) -> None:
        if not self.enabled:
            return None

        if not self.metrics_settings.webhook_url:
            return None

        try:
            latest_raw = self.generate_latest()
            metric_families = prometheus_client.parser.text_string_to_metric_families(
                latest_raw
            )
            metrics_dict: dict[str, Any] = {}
            for family in metric_families:
                for sample in family.samples:
                    # Skip if a specific metric name was requested and this isn't it
                    if metric_name and sample.name != metric_name:
                        continue

                    current_level = metrics_dict
                    if sample.labels:
                        # Skip if a specific kind was requested and this isn't it
                        if kind and sample.labels.get("kind") != kind:
                            continue

                        # Get the ordered labels from the registry
                        ordered_labels = _metrics_registry.get(
                            sample.name, (None, None, [])
                        )[2]

                        # Create nested dictionary structure based on ordered labels
                        for label_name in ordered_labels:
                            if label_name in sample.labels:
                                value = sample.labels[label_name]
                                if label_name not in current_level:
                                    current_level[label_name] = {}
                                current_level = current_level[label_name]
                                if value not in current_level:
                                    current_level[value] = {}
                                current_level = current_level[value]

                    current_level[sample.name] = sample.value

            # If no metrics were filtered, exit early
            if not metrics_dict.get("kind", {}):
                return None

            for kind_key, metrics in metrics_dict.get("kind", {}).items():
                # Skip if we're filtering by kind and this isn't the requested kind
                if kind and kind_key != kind:
                    continue

                event = {
                    "integration_type": self.integration_configuration.type,
                    "integration_identifier": self.integration_configuration.identifier,
                    "integration_version": self.integration_version,
                    "ocean_version": self.ocean_version,
                    "kind_identifier": kind_key,
                    "kind": "-".join(kind_key.split("-")[:-1]),
                    "event_id": self.event_id,
                    "sync_state": self.sync_state,
                    "metrics": metrics,
                }
                logger.info(f"Sending metrics to webhook {kind_key}: {event}")
                await AsyncClient().post(
                    url=self.metrics_settings.webhook_url, json=event
                )
        except Exception as e:
            logger.error(f"Error sending metrics to webhook: {e}")
