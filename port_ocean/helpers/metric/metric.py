from typing import Any, TYPE_CHECKING, Optional
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
    TOP_SORT = "top_sort"
    RESYNC = "resync"


class MetricType:
    DURATION = ("duration_seconds", "duration description", ["kind", "phase"])
    OBJECT_COUNT = ("object_count", "object_count description", ["kind", "phase"])
    ERROR_COUNT = ("error_count", "error_count description", ["kind", "phase"])
    SUCCESS = ("success", "success description", ["kind", "phase"])
    RATE_LIMIT_WAIT = (
        "rate_limit_wait_seconds",
        "rate_limit_wait description",
        ["kind", "phase", "endpoint"],
    )
    DELETED = ("deleted_count", "deleted description", ["kind", "phase"])


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
        for attr in dir(MetricType):
            if callable(getattr(MetricType, attr)) or attr.startswith("__"):
                continue
            name, description, lables = getattr(MetricType, attr)
            self.metrics[name] = Gauge(
                name, description, lables, registry=self.registry
            )

    def get_metric(self, name: str, lables: list[str]) -> Gauge | EmptyMetric:
        if not self.enabled:
            return EmptyMetric()
        metrics = self.metrics.get(name)
        if not metrics:
            return EmptyMetric()
        return metrics.labels(self.get_kind(), *lables)

    def create_mertic_router(self) -> APIRouter:
        if not self.enabled:
            return APIRouter()
        router = APIRouter()

        @router.get("/")
        async def prom_metrics() -> str:
            return self.generate_latest()

        return router

    def get_kind(self) -> str:
        try:
            return f"{resource.resource.kind}-{resource.resource.index}"
        except ResourceContextNotFoundError:
            return "__runtime__"

    def generate_latest(self) -> str:
        return prometheus_client.openmetrics.exposition.generate_latest(
            self.registry
        ).decode()

    async def flush(self) -> None:
        if not self.enabled:
            return None

        latest_raw = self.generate_latest()
        metric_families = prometheus_client.parser.text_string_to_metric_families(
            latest_raw
        )
        metrics_dict: dict[str, Any] = {}
        for family in metric_families:
            for sample in family.samples:
                current_level = metrics_dict
                if sample.labels:
                    # Create nested dictionary structure based on labels
                    for key, value in sample.labels.items():
                        if key not in current_level:
                            current_level[key] = {}
                        current_level = current_level[key]
                        if value not in current_level:
                            current_level[value] = {}
                        current_level = current_level[value]

                current_level[sample.name] = sample.value

        if self.metrics_settings.webhook_url:
            for kind, metrics in metrics_dict.get("kind", {}).items():
                event = {
                    "integration_type": self.integration_configuration.type,
                    "integration_identifier": self.integration_configuration.identifier,
                    "integration_version": self.integration_version,
                    "ocean_version": self.ocean_version,
                    "kind_identifier": kind,
                    "kind": "-".join(kind.split("-")[:-1]),
                    "metrics": metrics,
                }
                logger.debug(f"Sending metrics to webhook {kind}")
                await AsyncClient().post(
                    url=self.metrics_settings.webhook_url, json=event
                )
