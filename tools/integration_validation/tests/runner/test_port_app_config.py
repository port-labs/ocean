from typing import Any

import pytest

from tools.integration_validation.runner.errors import ValidationSetupError
from tools.integration_validation.runner.models import ScenarioDefinition
from tools.integration_validation.runner.port_app_config import (
    build_scenario_port_app_config,
)

BASE_CONFIG: dict[str, Any] = {
    "deleteDependentEntities": True,
    "resources": [
        {
            "kind": "team",
            "selector": {"query": "true", "includeMembers": False},
            "port": {"entity": {"mappings": {"blueprint": '"team"', "title": ".name"}}},
        },
        {
            "kind": "user",
            "selector": {"query": "true"},
            "port": {"entity": {"mappings": {"blueprint": '"user"'}}},
        },
    ],
}


def _scenario(**kwargs: Any) -> ScenarioDefinition:
    return ScenarioDefinition(routes=["routes/team.yaml"], **kwargs)


def test_without_kinds_or_overrides_returns_a_copy_of_the_defaults() -> None:
    config = build_scenario_port_app_config(BASE_CONFIG, "happy", _scenario())

    assert config == BASE_CONFIG
    assert config is not BASE_CONFIG


def test_kinds_filter_resources() -> None:
    config = build_scenario_port_app_config(
        BASE_CONFIG, "happy", _scenario(kinds=["user"])
    )

    assert [r["kind"] for r in config["resources"]] == ["user"]
    assert config["deleteDependentEntities"] is True


def test_unknown_kind_is_rejected() -> None:
    with pytest.raises(ValidationSetupError, match="monitor"):
        build_scenario_port_app_config(
            BASE_CONFIG, "happy", _scenario(kinds=["monitor"])
        )


def test_overrides_deep_merge_into_matching_kind() -> None:
    scenario = _scenario(
        port_app_config_overrides=[
            {
                "kind": "team",
                "selector": {"includeMembers": True},
                "port": {"entity": {"mappings": {"title": ".attributes.name"}}},
            }
        ]
    )

    config = build_scenario_port_app_config(BASE_CONFIG, "members", scenario)

    team = config["resources"][0]
    assert team["selector"] == {"query": "true", "includeMembers": True}
    assert team["port"]["entity"]["mappings"] == {
        "blueprint": '"team"',
        "title": ".attributes.name",
    }
    assert BASE_CONFIG["resources"][0]["selector"]["includeMembers"] is False


def test_override_for_filtered_out_kind_is_rejected() -> None:
    scenario = _scenario(
        kinds=["user"],
        port_app_config_overrides=[
            {"kind": "team", "selector": {"includeMembers": True}}
        ],
    )

    with pytest.raises(ValidationSetupError, match="override for kind 'team'"):
        build_scenario_port_app_config(BASE_CONFIG, "members", scenario)


def test_override_without_kind_is_rejected() -> None:
    scenario = _scenario(port_app_config_overrides=[{"selector": {"query": "false"}}])

    with pytest.raises(ValidationSetupError, match="needs a 'kind'"):
        build_scenario_port_app_config(BASE_CONFIG, "broken", scenario)
