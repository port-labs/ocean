import os
from unittest.mock import patch

from aws.config.live_events import LIVE_EVENTS_API_KEY_ENV, get_live_events_api_key


def test_get_live_events_api_key_from_integration_config() -> None:
    with patch("aws.config.live_events.ocean") as mock_ocean:
        mock_ocean.integration_config = {"live_events_api_key": "from-config"}
        with patch.dict(os.environ, {}, clear=True):
            assert get_live_events_api_key() == "from-config"


def test_get_live_events_api_key_from_env_when_missing_from_config() -> None:
    with patch("aws.config.live_events.ocean") as mock_ocean:
        mock_ocean.integration_config = {}
        with patch.dict(os.environ, {LIVE_EVENTS_API_KEY_ENV: "from-env"}, clear=True):
            assert get_live_events_api_key() == "from-env"


def test_get_live_events_api_key_returns_none_when_unset() -> None:
    with patch("aws.config.live_events.ocean") as mock_ocean:
        mock_ocean.integration_config = {}
        with patch.dict(os.environ, {}, clear=True):
            assert get_live_events_api_key() is None
