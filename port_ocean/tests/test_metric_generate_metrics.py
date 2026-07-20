"""Tests for Metrics.generate_metrics, especially kindIndex derivation from kindIdentifier."""

from unittest.mock import MagicMock

from port_ocean.helpers.metric.metric import (
    MetricPhase,
    MetricType,
    Metrics,
)


def _make_metrics() -> Metrics:
    metrics_settings = MagicMock()
    metrics_settings.enabled = True
    integration_configuration = MagicMock()
    integration_configuration.type = "test-integration"
    integration_configuration.identifier = "test-id"
    port_client = MagicMock()
    return Metrics(
        metrics_settings=metrics_settings,
        integration_configuration=integration_configuration,
        port_client=port_client,
        multiprocessing_enabled=False,
    )


def test_generate_metrics_kind_index_two_digits() -> None:
    """kindIdentifier 'name-12' must yield kindIndex=12 (not 2 from last character)."""
    metrics = _make_metrics()
    metrics.set_metric(
        MetricType.DURATION_NAME,
        ["name-12", MetricPhase.RESYNC],
        1.0,
    )
    events = metrics.generate_metrics()
    assert len(events) == 1
    assert events[0]["kindIdentifier"] == "name-12"
    assert events[0]["kind"] == "name"
    assert events[0]["kindIndex"] == 12


def test_generate_metrics_kind_index_single_digit() -> None:
    """kindIdentifier 'project-0' must yield kindIndex=0."""
    metrics = _make_metrics()
    metrics.set_metric(
        MetricType.DURATION_NAME,
        ["project-0", MetricPhase.RESYNC],
        1.0,
    )
    events = metrics.generate_metrics()
    assert len(events) == 1
    assert events[0]["kindIdentifier"] == "project-0"
    assert events[0]["kind"] == "project"
    assert events[0]["kindIndex"] == 0


def test_generate_metrics_kind_index_no_hyphen() -> None:
    """kindIdentifier without hyphen (e.g. __runtime__) must yield kindIndex=0."""
    metrics = _make_metrics()
    metrics.set_metric(
        MetricType.DURATION_NAME,
        ["__runtime__", MetricPhase.RESYNC],
        1.0,
    )
    events = metrics.generate_metrics()
    assert len(events) == 1
    assert events[0]["kindIdentifier"] == "__runtime__"
    assert events[0]["kind"] == "__runtime__"
    assert events[0]["kindIndex"] == 0


def test_generate_metrics_kind_index_multiple_kinds() -> None:
    """Multiple kindIdentifiers: name-12 (kindIndex 12), repository-1 (kindIndex 1)."""
    metrics = _make_metrics()
    metrics.set_metric(
        MetricType.DURATION_NAME,
        ["name-12", MetricPhase.RESYNC],
        1.0,
    )
    metrics.set_metric(
        MetricType.DURATION_NAME,
        ["repository-1", MetricPhase.RESYNC],
        2.0,
    )
    events = metrics.generate_metrics()
    assert len(events) == 2
    by_kind_id = {e["kindIdentifier"]: e for e in events}
    assert by_kind_id["name-12"]["kind"] == "name"
    assert by_kind_id["name-12"]["kindIndex"] == 12
    assert by_kind_id["repository-1"]["kind"] == "repository"
    assert by_kind_id["repository-1"]["kindIndex"] == 1
