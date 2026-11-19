from typing import NotRequired, Optional, TypedDict

from coralogix.helpers.utils import MetricsSource


class ServiceOptions(TypedDict):
    window: str
    lookback: NotRequired[str]
    metrics_source: NotRequired[MetricsSource]
    label_filter: NotRequired[str]


class SloOptions(TypedDict):
    include_status: bool


class CaseOptions(TypedDict):
    days_back: int
    statuses: NotRequired[Optional[list[str]]]
