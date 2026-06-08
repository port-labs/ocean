from unittest.mock import patch

from exporter_factory import create_ai_commit_metrics_exporter


def test_create_ai_commit_metrics_exporter() -> None:
    with patch("exporter_factory.create_cursor_client"):
        exporter = create_ai_commit_metrics_exporter()
        assert exporter is not None
