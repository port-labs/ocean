import json

import pytest

from port_ocean.tests.smoke.configset_registry import (
    list_configset_names,
    load_configset,
    ocean_config_env,
)


def test_configsets_are_discovered() -> None:
    assert {"actions", "resync"}.issubset(set(list_configset_names()))


def test_resync_configset() -> None:
    configset = load_configset("resync")
    assert configset.wait_for_resync is True
    env = ocean_config_env(configset.ocean)
    assert json.loads(env["OCEAN__EVENT_LISTENER"])["type"] == "ONCE"
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "false"


def test_actions_configset() -> None:
    configset = load_configset("actions")
    assert configset.wait_for_resync is True
    env = ocean_config_env(configset.ocean)
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "true"
    assert env["OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED"] == "true"


def test_unknown_configset_raises() -> None:
    with pytest.raises(ValueError, match="Unknown smoke configset"):
        load_configset("does-not-exist")
