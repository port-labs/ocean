import pytest
from pydantic.v1 import ValidationError

from coralogix.helpers.utils import MetricsSource
from integration import (
    CaseSelector,
    CoralogixPortAppConfig,
    ServiceSelector,
    SloSelector,
)


def test_selector_defaults() -> None:
    service = ServiceSelector(query="true")
    assert (service.window, service.lookback) == ("1h", "30d")
    assert service.metrics_source == MetricsSource.AUTO
    assert SloSelector(query="true").include_status is True
    case = CaseSelector(query="true")
    assert case.days_back == 30 and case.statuses is None


def test_selector_aliases() -> None:
    selector = CaseSelector(query="true", daysBack=7, statuses=["CASE_STATUS_ACTIVE"])
    assert selector.days_back == 7
    service = ServiceSelector.parse_obj(
        {
            "query": "true",
            "labelFilter": 'a="b"',
            "metricsSource": "compact_span_metrics",
        }
    )
    assert service.label_filter == 'a="b"'
    assert service.metrics_source == MetricsSource.COMPACT_SPAN_METRICS


@pytest.mark.parametrize(
    "label_filter",
    ['{k8s_cluster_name="prod"}', 'k8s_cluster_name="prod"} or up{', "not a matcher"],
)
def test_label_filter_rejects_breakout(label_filter: str) -> None:
    with pytest.raises(ValidationError):
        ServiceSelector.parse_obj({"query": "true", "labelFilter": label_filter})


@pytest.mark.parametrize("field", ["window", "lookback"])
@pytest.mark.parametrize("value", ["1x", "h", "", "1.5h"])
def test_service_range_validation(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        ServiceSelector.parse_obj({"query": "true", field: value})


def test_service_metrics_source_validation() -> None:
    with pytest.raises(ValidationError):
        ServiceSelector.parse_obj({"query": "true", "metricsSource": "prometheus"})


def test_case_status_validation() -> None:
    with pytest.raises(ValidationError):
        CaseSelector(query="true", statuses=["OPEN"])


def test_default_port_app_config_parses() -> None:
    import pathlib

    import yaml  # type: ignore[import-untyped]

    raw = yaml.safe_load(
        (
            pathlib.Path(__file__).parent.parent / ".port/resources/port-app-config.yml"
        ).read_text()
    )
    config = CoralogixPortAppConfig.parse_obj(raw)
    assert [r.kind for r in config.resources] == [
        "service",
        "slo",
        "alert-definition",
        "case",
    ]
