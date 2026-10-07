import json

import pytest

from port_ocean.tests.smoke.configset_registry import (
    list_configset_names,
    load_configset,
    ocean_config_env,
)


def test_configsets_are_discovered() -> None:
    assert {"workflows", "resync"}.issubset(set(list_configset_names()))


def test_resync_configset() -> None:
    configset = load_configset("resync")
    assert configset.wait_for_resync is True
    env = ocean_config_env(configset.ocean)
    assert json.loads(env["OCEAN__EVENT_LISTENER"])["type"] == "ONCE"
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "false"


def test_workflows_configset() -> None:
    configset = load_configset("workflows")
    assert configset.wait_for_resync is False
    env = ocean_config_env(configset.ocean)
    assert json.loads(env["OCEAN__EVENT_LISTENER"])["resync_on_start"] is False
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "true"
    assert env["OCEAN__INTEGRATION__TYPE"] == "fake-integration"
    assert env["OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED"] == "false"


def test_unknown_configset_raises() -> None:
    with pytest.raises(ValueError, match="Unknown smoke configset"):
        load_configset("does-not-exist")
