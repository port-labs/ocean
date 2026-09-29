import json

import pytest

from port_ocean.tests.smoke.scenario_registry import (
    list_scenario_names,
    load_scenario,
    ocean_config_env,
)


def test_scenarios_are_discovered() -> None:
    assert {"actions", "once", "resync"}.issubset(set(list_scenario_names()))


def test_resync_scenario_uses_polling_without_actions() -> None:
    scenario = load_scenario("resync")
    assert scenario.lifecycle == "daemon"
    assert scenario.suffix == "resync"
    assert scenario.wait_for_resync is True
    assert scenario.tests == ("port_ocean/tests/smoke/test_resync.py",)

    env = ocean_config_env(scenario.ocean)
    assert json.loads(env["OCEAN__EVENT_LISTENER"])["type"] == "POLLING"
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "false"
    assert env["OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED"] == "false"


def test_actions_scenario_enables_actions_and_live_events() -> None:
    scenario = load_scenario("actions")
    assert scenario.lifecycle == "daemon"
    assert scenario.tests == ("port_ocean/tests/smoke/test_actions.py",)

    env = ocean_config_env(scenario.ocean)
    assert json.loads(env["OCEAN__EVENT_LISTENER"])["type"] == "POLLING"
    assert env["OCEAN__ACTIONS_PROCESSOR__ENABLED"] == "true"
    assert env["OCEAN__LIVE_EVENTS__IS_REDIS_STREAM_CONSUMER_ENABLED"] == "true"


def test_once_scenario_has_no_tests() -> None:
    scenario = load_scenario("once")
    assert scenario.lifecycle == "once"
    assert scenario.tests == ()


def test_unknown_scenario_raises() -> None:
    with pytest.raises(ValueError, match="Unknown smoke scenario"):
        load_scenario("does-not-exist")
