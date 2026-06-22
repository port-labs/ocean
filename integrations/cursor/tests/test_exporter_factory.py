from unittest.mock import patch

from exporter_factory import (
    create_team_model_usage_exporter,
    create_user_model_usage_exporter,
)


def test_create_team_model_usage_exporter() -> None:
    with patch("exporter_factory.create_cursor_client"):
        exporter = create_team_model_usage_exporter()
        assert exporter is not None


def test_create_user_model_usage_exporter() -> None:
    with patch("exporter_factory.create_cursor_client"):
        exporter = create_user_model_usage_exporter()
        assert exporter is not None
