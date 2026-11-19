from typing import Literal, Optional

from pydantic.v1 import Field, validator
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.integrations.base import BaseIntegration

from coralogix.helpers.utils import MetricsSource, ObjectKind, validate_label_filter

CASE_STATUSES = (
    "CASE_STATUS_PENDING_ACTIVATION",
    "CASE_STATUS_ACTIVE",
    "CASE_STATUS_ACKNOWLEDGED",
    "CASE_STATUS_RESOLVED",
    "CASE_STATUS_CLOSED",
)


class ServiceSelector(Selector):
    lookback: str = Field(
        default="30d",
        title="Discovery lookback",
        description="Services that emitted any span in this range are synced, e.g. 1d, 7d, 30d.",
    )
    window: str = Field(
        default="1h",
        title="Metrics window",
        description="PromQL range for request rate, error rate and P95 latency, e.g. 15m, 1h, 1d. Services idle in this window are synced with zero requests.",
    )
    metrics_source: MetricsSource = Field(
        default=MetricsSource.AUTO,
        alias="metricsSource",
        title="Span metrics source",
        description="Which span metrics to read: auto (detect), span_metrics (calls_total, duration_ms_*), compact_span_metrics (compact_calls_total, compact_duration_ms_*) or otel_spanmetrics_connector (traces_span_metrics_*).",
    )
    label_filter: str = Field(
        default="",
        alias="labelFilter",
        title="Span metrics label filter",
        description='Comma-separated PromQL matchers added to every query, without braces, e.g. k8s_cluster_name="prod".',
    )

    @validator("label_filter")
    def _check_label_filter(cls, value: str) -> str:
        return validate_label_filter(value)

    @validator("window", "lookback")
    def _check_range(cls, value: str) -> str:
        if not value or value[-1] not in "smhdw" or not value[:-1].isdigit():
            raise ValueError("must be a PromQL range like 15m, 1h or 7d")
        return value


class ServiceResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SERVICE] = Field(
        title="Coralogix Service",
        description="APM services and their RED metrics, from Coralogix span metrics.",
    )
    selector: ServiceSelector = Field(
        title="Service Selector",
        description="Metrics window and label filter for the span-metrics queries.",
    )


class SloSelector(Selector):
    include_status: bool = Field(
        default=True,
        alias="includeStatus",
        title="Include compliance status",
        description="Fetch current compliance and remaining error budget for each SLO (one extra API call per SLO).",
    )


class SloResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.SLO] = Field(
        title="Coralogix SLO",
        description="Service level objectives from the Coralogix SLO Center.",
    )
    selector: SloSelector = Field(
        title="SLO Selector",
        description="Whether to fetch compliance and error budget per SLO.",
    )


class AlertDefinitionResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.ALERT_DEFINITION] = Field(
        title="Coralogix Alert Definition",
        description="Coralogix alert definitions.",
    )


class CaseSelector(Selector):
    days_back: int = Field(
        default=30,
        alias="daysBack",
        ge=1,
        le=365,
        title="Days back",
        description="Sync cases created in the last N days.",
    )
    statuses: Optional[list[str]] = Field(
        default=None,
        title="Statuses",
        description=f"Only sync cases in these statuses. Default: all. Allowed: {', '.join(CASE_STATUSES)}.",
    )

    @validator("statuses")
    def _check_statuses(cls, value: Optional[list[str]]) -> Optional[list[str]]:
        invalid = [s for s in value or [] if s not in CASE_STATUSES]
        if invalid:
            raise ValueError(f"Unknown case statuses: {invalid}")
        return value


class CaseResourceConfig(ResourceConfig):
    kind: Literal[ObjectKind.CASE] = Field(
        title="Coralogix Case",
        description="Coralogix cases opened by alerts.",
    )
    selector: CaseSelector = Field(
        title="Case Selector",
        description="Time range and statuses of the cases to sync.",
    )


class CoralogixPortAppConfig(PortAppConfig):
    resources: list[
        ServiceResourceConfig
        | SloResourceConfig
        | AlertDefinitionResourceConfig
        | CaseResourceConfig
    ] = Field(
        default_factory=list
    )  # type: ignore[assignment]


class CoralogixIntegration(BaseIntegration):
    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = CoralogixPortAppConfig
