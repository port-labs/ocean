import json

import pytest

from port_ocean.tests.smoke.config_registry import (
    list_config_names,
    load_config,
    ocean_config_env,
)


def test_configs_are_discovered() -> None:
    assert {"actions", "once", "resync"}.issubset(set(list_config_names()))


def test_resync_config() -> None:
    config = load_config("resync")
    assert config.lifecycle == "daemon"
    assert config.wait_for_resync is True
    env = ocean_config_env(config.ocean)
    assert json.loads(env["OCEAN__EVENT_LISTENER"])["type"] == "POLLING"
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "false"


def test_actions_config() -> None:
    config = load_config("actions")
    assert config.lifecycle == "daemon"
    assert config.wait_for_resync is False
    env = ocean_config_env(config.ocean)
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "true"
    assert env["OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED"] == "true"


def test_once_config_lifecycle_from_event_listener() -> None:
    config = load_config("once")
    assert config.lifecycle == "once"


def test_unknown_config_raises() -> None:
    with pytest.raises(ValueError, match="Unknown smoke config"):
        load_config("does-not-exist")
