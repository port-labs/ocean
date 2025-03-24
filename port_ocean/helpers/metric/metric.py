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


class MetricType:
    # Define metric names as constants
    DURATION_NAME = "duration_seconds"
    OBJECT_COUNT_NAME = "object_count"
    ERROR_COUNT_NAME = "error_count"
    SUCCESS_NAME = "success"
    RATE_LIMIT_WAIT_NAME = "rate_limit_wait_seconds"
    DELETION_COUNT_NAME = "deletion_count"


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
        ["kind", "phase"],
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

                        # Create nested dictionary structure based on labels
                        for key, value in sample.labels.items():
                            if key not in current_level:
                                current_level[key] = {}
                            current_level = current_level[key]
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
                    "metrics": metrics,
                }
                logger.info(f"Sending metrics to webhook {kind_key}: {event}")
                await AsyncClient().post(
                    url=self.metrics_settings.webhook_url, json=event
                )
        except Exception as e:
            logger.error(f"Error sending metrics to webhook: {e}")
