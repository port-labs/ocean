from pathlib import Path

import pytest
import yaml  # type: ignore[import-untyped]
from pydantic.v1 import ValidationError

from incident_io.helpers.utils import ObjectKind
from integration import (
    AlertSelector,
    IncidentIoPortAppConfig,
    IncidentSelector,
    UserSelector,
)


def test_selector_defaults() -> None:
    incident = IncidentSelector(query="true")
    assert incident.days_back == 90
    assert incident.status_categories is None
    assert incident.severities is None
    assert incident.include_test is False
    assert UserSelector(query="true").include_inactive is False


def test_selector_aliases() -> None:
    selector = IncidentSelector.parse_obj(
        {
            "query": "true",
            "daysBack": 30,
            "statusCategories": ["live"],
            "severities": ["Critical", "Major"],
            "includeTest": True,
        }
    )
    assert selector.days_back == 30
    assert selector.status_categories == ["live"]
    assert selector.severities == ["Critical", "Major"]
    assert selector.include_test is True
    user = UserSelector.parse_obj({"query": "true", "includeInactive": True})
    assert user.include_inactive is True


def test_empty_status_categories_mean_all() -> None:
    selector = IncidentSelector(query="true", statusCategories=[])
    assert selector.status_categories == []


def test_unknown_status_category_is_rejected() -> None:
    with pytest.raises(ValidationError):
        IncidentSelector.parse_obj({"query": "true", "statusCategories": ["active"]})


def test_days_back_bounds() -> None:
    for selector in (IncidentSelector, AlertSelector):
        with pytest.raises(ValidationError):
            selector(query="true", daysBack=0)
        with pytest.raises(ValidationError):
            selector(query="true", daysBack=1826)
        assert selector(query="true", daysBack=1825).days_back == 1825


def test_default_port_app_config_parses() -> None:
    raw = yaml.safe_load(
        (
            Path(__file__).parent.parent / ".port/resources/port-app-config.yml"
        ).read_text()
    )
    config = IncidentIoPortAppConfig.parse_obj(raw)
    assert [resource.kind for resource in config.resources] == [
        ObjectKind.USER,
        ObjectKind.TEAM,
        ObjectKind.SCHEDULE,
        ObjectKind.ALERT,
        ObjectKind.INCIDENT,
    ]
    alert = next(
        resource for resource in config.resources if resource.kind == ObjectKind.ALERT
    )
    assert isinstance(alert.selector, AlertSelector)
    assert alert.selector.days_back == 90
    incident = next(
        resource
        for resource in config.resources
        if resource.kind == ObjectKind.INCIDENT
    )
    assert isinstance(incident.selector, IncidentSelector)
    assert incident.selector.days_back == 90


def test_alert_selector_defaults_and_rejects_unknown_status() -> None:
    selector = AlertSelector(query="true")
    assert selector.days_back == 90
    assert selector.statuses is None
    chosen = AlertSelector.parse_obj(
        {"query": "true", "daysBack": 7, "statuses": ["firing"]}
    )
    assert chosen.days_back == 7
    assert chosen.statuses == ["firing"]
    assert AlertSelector(query="true", statuses=[]).statuses == []
    with pytest.raises(ValidationError):
        AlertSelector.parse_obj({"query": "true", "statuses": ["open"]})
