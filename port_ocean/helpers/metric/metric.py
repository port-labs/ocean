from fastapi import APIRouter
from port_ocean.exceptions.context import ResourceContextNotFoundError
import prometheus_client

from loguru import logger
from port_ocean.context import resource
from prometheus_client import Gauge
import prometheus_client.openmetrics
import prometheus_client.openmetrics.exposition
import prometheus_client.parser


class MetricPhase:
    EXTRACT = "extract"
    TRANSFORM = "transform"
    LOAD = "load"
    TOP_SORT = "top_sort"


class MetricType:
    DURATION = ("duration_seconds", "duration description", ["kind", "phase"])
    OBJECT_COUNT = ("object_count", "object_count description", ["kind", "phase"])
    ERROR_COUNT = ("error_count", "error_count description", ["kind", "phase"])
    RATE_LIMIT_WAIT = (
        "rate_limit_wait_seconds",
        "rate_limit_wait description",
        ["kind", "phase", "endpoint"],
    )
    FAILED_COUNT = ("failed_count", "failed_count description", ["kind", "phase"])
    INPUT_COUNT = (
        "input_count",
        "input_count description",
        ["kind", "phase"],
    )
    UPSERTED = ("upserted_count", "upserted description", ["kind", "phase"])
    DELETED = ("deleted_count", "deleted description", ["kind", "phase"])
    REQUESTS = (
        "http_requests_count",
        "requests description",
        ["kind", "status", "endpoint"],
    )


class Metrics:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled

        self.registry = prometheus_client.CollectorRegistry()
        self.metrics: dict[str, Gauge] = {}
        self.load_metrics()

    def load_metrics(self):
        if not self.enabled:
            return None
        for attr in dir(MetricType):
            if callable(getattr(MetricType, attr)) or attr.startswith("__"):
                continue
            name, description, lables = getattr(MetricType, attr)
            self.metrics[name] = Gauge(
                name, description, lables, registry=self.registry
            )

    def get_metric(self, name, lables: list[str]):
        if not self.enabled:

            class Empty:
                def inc(self, *args):
                    return None

            return Empty()
        return self.metrics.get(name).labels(self.get_kind(), *lables)

    def create_mertic_router(self):
        if not self.enabled:
            return APIRouter()
        router = APIRouter()

        @router.get("/")
        async def prom_metrics():
            return self.generate_latest()

        return router

    def get_kind(self) -> str:
        try:
            return f"{resource.resource.kind}-{resource.resource.index}"
        except ResourceContextNotFoundError:
            return ""

    def generate_latest(self):
        return prometheus_client.openmetrics.exposition.generate_latest(
            self.registry
        ).decode()

    async def flush(self) -> None:
        latest_raw = self.generate_latest()
        metric_families = prometheus_client.parser.text_string_to_metric_families(
            latest_raw
        )
        metrics_dict = {}
        for family in metric_families:
            for sample in family.samples:
                label_parts = [str(v) for _, v in sample.labels.items()]
                label_str = "__".join(label_parts)

                dict_key = f"{sample.name}__{label_str}" if label_str else sample.name

                metrics_dict[dict_key] = sample.value
        logger.info(f"prom metrics - {metrics_dict}")
