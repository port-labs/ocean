from unittest.mock import MagicMock, patch

import pytest

import port_ocean.helpers.metric.metric as metric_module
from port_ocean.helpers.metric.metric import Metrics


def _make_metrics(is_self_hosted: bool = False) -> Metrics:
    return Metrics(
        metrics_settings=MagicMock(),
        integration_configuration=MagicMock(),
        port_client=MagicMock(),
        is_self_hosted=is_self_hosted,
    )


def test_metrics_warns_when_prometheus_multiproc_dir_is_set_on_self_hosted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/ocean/prometheus/metrics")
    metric_module._prometheus_multiproc_dir_warning_issued = False

    with patch("port_ocean.helpers.metric.metric.logger") as mock_logger:
        _make_metrics(is_self_hosted=True)

    mock_logger.warning.assert_called_once()
    message = mock_logger.warning.call_args[0][0]
    assert "PROMETHEUS_MULTIPROC_DIR" in message
    assert "leftover" in message
    assert (
        mock_logger.warning.call_args[1]["prometheus_multiproc_dir"]
        == "/tmp/ocean/prometheus/metrics"
    )


def test_metrics_does_not_warn_on_saas_when_prometheus_multiproc_dir_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PROMETHEUS_MULTIPROC_DIR", "/tmp/ocean/prometheus/metrics")
    metric_module._prometheus_multiproc_dir_warning_issued = False

    with patch("port_ocean.helpers.metric.metric.logger") as mock_logger:
        _make_metrics(is_self_hosted=False)

    mock_logger.warning.assert_not_called()


def test_metrics_does_not_warn_when_prometheus_multiproc_dir_is_not_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("PROMETHEUS_MULTIPROC_DIR", raising=False)
    metric_module._prometheus_multiproc_dir_warning_issued = False

    with patch("port_ocean.helpers.metric.metric.logger") as mock_logger:
        _make_metrics(is_self_hosted=True)

    mock_logger.warning.assert_not_called()
