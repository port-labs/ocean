import re
from enum import StrEnum
from typing import NamedTuple, Optional
from urllib.parse import urlparse

MGMT_API_PREFIX = "mgmt/openapi/5"
METRICS_API_PREFIX = "metrics/api/v1"
PERMISSIONS_DOCS_URL = "https://coralogix.com/docs/user-guides/aaa/access-control/permissions/permissions-list/"


class ObjectKind(StrEnum):
    SERVICE = "service"
    SLO = "slo"
    ALERT_DEFINITION = "alert-definition"
    CASE = "case"


class MetricsSource(StrEnum):
    AUTO = "auto"
    SPAN_METRICS = "span_metrics"
    COMPACT_SPAN_METRICS = "compact_span_metrics"
    OTEL_SPANMETRICS_CONNECTOR = "otel_spanmetrics_connector"


class SpanMetricNames(NamedTuple):
    calls: str
    duration: str  # histogram base name; _bucket is appended


# Metric names per span-metrics setup, in auto-detection order (richest labels first).
# https://coralogix.com/docs/user-guides/apm/getting-started/span-metrics/
# https://coralogix.com/docs/user-guides/apm/getting-started/using-compact-span-metric/
SPAN_METRIC_NAMES: dict[MetricsSource, SpanMetricNames] = {
    MetricsSource.SPAN_METRICS: SpanMetricNames("calls_total", "duration_ms"),
    MetricsSource.COMPACT_SPAN_METRICS: SpanMetricNames(
        "compact_calls_total", "compact_duration_ms"
    ),
    MetricsSource.OTEL_SPANMETRICS_CONNECTOR: SpanMetricNames(
        "traces_span_metrics_calls_total", "traces_span_metrics_duration_milliseconds"
    ),
}


# Endpoint prefix -> Coralogix permission needed to read it (permissions list docs).
REQUIRED_PERMISSIONS: dict[str, str] = {
    f"{MGMT_API_PREFIX}/slo/": "SLO:READCONFIG",
    f"{MGMT_API_PREFIX}/alerts/": "ALERTS:READCONFIG",
    f"{MGMT_API_PREFIX}/cases/": "CASES:READ",
    f"{METRICS_API_PREFIX}/": "METRICS.DATA-API#HIGH:READDATA",
}

# One PromQL matcher, then more separated by commas. Braces are rejected so a
# filter cannot close the selector and append another query.
_PROMQL_MATCHER = r'[a-zA-Z_][a-zA-Z0-9_]*\s*(?:=~|!~|!=|=)\s*"(?:[^"\\]|\\.)*"'
_LABEL_FILTER = re.compile(rf"^{_PROMQL_MATCHER}(?:\s*,\s*{_PROMQL_MATCHER})*$")


def validate_label_filter(value: str) -> str:
    """Accept an empty filter or comma-separated PromQL matchers, without braces."""
    text = value.strip()
    if not text:
        return ""
    if _LABEL_FILTER.fullmatch(text) is None:
        raise ValueError(
            "labelFilter must be comma-separated PromQL matchers such as "
            'k8s_cluster_name="prod", without braces'
        )
    return text


def required_permission(endpoint: str) -> Optional[str]:
    endpoint = endpoint.lstrip("/")
    for prefix, permission in REQUIRED_PERMISSIONS.items():
        if endpoint.startswith(prefix):
            return permission
    return None


# Coralogix web app domain (after "<team>.") -> API host.
# https://coralogix.com/docs/user-guides/account-management/account-settings/coralogix-domain/
_APP_DOMAIN_TO_API_HOST: dict[str, str] = {
    "coralogix.com": "api.eu1.coralogix.com",
    "app.eu2.coralogix.com": "api.eu2.coralogix.com",
    "app.coralogix.us": "api.us1.coralogix.com",
    "app.cx498.coralogix.com": "api.us2.coralogix.com",
    "app.us3.coralogix.com": "api.us3.coralogix.com",
    "app.coralogix.in": "api.ap1.coralogix.com",
    "app.coralogixsg.com": "api.ap2.coralogix.com",
    "app.ap3.coralogix.com": "api.ap3.coralogix.com",
    "app.gov1.coralogixgov.us": "api.gov1.coralogixgov.us",
}


def resolve_api_base_url(url: str) -> str:
    """Return the Coralogix API base (https://api.<region>...) for either an API
    URL or the team URL the user opens in the browser."""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    host = (parsed.hostname or "").lower()
    if host.startswith("api."):
        return f"https://{host}"
    for app_domain, api_host in sorted(
        _APP_DOMAIN_TO_API_HOST.items(), key=lambda item: -len(item[0])
    ):
        if host == app_domain or host.endswith(f".{app_domain}"):
            return f"https://{api_host}"
    raise ValueError(
        f"Unrecognized Coralogix URL '{url}'. Use your API URL "
        "(for example https://api.eu2.coralogix.com) or your team URL "
        "(for example https://myteam.app.eu2.coralogix.com)."
    )
