import json

import pytest

from tools.integration_validation.runner.integration_config_env import (
    build_sail_subprocess_env,
    integration_config_env_vars,
    merge_scenario_integration_config,
    render_integration_config_values,
)


def test_render_integration_config_replaces_mock_base_url() -> None:
    rendered = render_integration_config_values(
        {"exampleBaseUrl": "{{mock_base_url}}/api", "count": 1},
        mock_base_url="http://127.0.0.1:9000",
    )
    assert rendered == {"exampleBaseUrl": "http://127.0.0.1:9000/api", "count": 1}


def test_render_integration_config_replaces_mock_base_url_in_lists() -> None:
    rendered = render_integration_config_values(
        {
            "organizationUrls": [
                "{{mock_base_url}}/org-a",
                {"nestedBaseUrl": "{{mock_base_url}}/nested"},
            ]
        },
        mock_base_url="http://127.0.0.1:9000",
    )
    assert rendered == {
        "organizationUrls": [
            "http://127.0.0.1:9000/org-a",
            {"nestedBaseUrl": "http://127.0.0.1:9000/nested"},
        ]
    }

    env = integration_config_env_vars(rendered)
    assert json.loads(env["OCEAN__INTEGRATION__CONFIG__ORGANIZATION_URLS"]) == [
        "http://127.0.0.1:9000/org-a",
        {"nestedBaseUrl": "http://127.0.0.1:9000/nested"},
    ]


def test_integration_config_env_vars_use_ocean_prefix() -> None:
    env = integration_config_env_vars(
        {"datadogBaseUrl": "http://example.com", "datadogApiKey": "key"}
    )
    assert env == {
        "OCEAN__INTEGRATION__CONFIG__DATADOG_BASE_URL": "http://example.com",
        "OCEAN__INTEGRATION__CONFIG__DATADOG_API_KEY": "key",
    }


def test_build_sail_subprocess_env_blocks_base_url_and_sets_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OCEAN__BASE_URL", "https://should-not-propagate")
    monkeypatch.setenv("OCEAN__PORT__CLIENT_ID", "client")

    env = build_sail_subprocess_env(
        integration_identifier="validate-sample-happy",
        integration_config={"exampleBaseUrl": "{{mock_base_url}}"},
        mock_base_url="http://127.0.0.1:9000",
    )

    assert "OCEAN__BASE_URL" not in env
    assert env["OCEAN__INTEGRATION__IDENTIFIER"] == "validate-sample-happy"
    assert env["OCEAN__INITIALIZE_PORT_RESOURCES"] == "false"
    assert env["OCEAN__EVENT_LISTENER__TYPE"] == "ONCE"
    assert (
        env["OCEAN__INTEGRATION__CONFIG__EXAMPLE_BASE_URL"] == "http://127.0.0.1:9000"
    )
    assert env["OCEAN__PORT__CLIENT_ID"] == "client"


def test_merge_scenario_integration_config_applies_overrides() -> None:
    merged = merge_scenario_integration_config(
        {"exampleBaseUrl": "{{mock_base_url}}", "region": "us"},
        {"region": "eu", "extra": 1},
    )
    assert merged == {
        "exampleBaseUrl": "{{mock_base_url}}",
        "region": "eu",
        "extra": 1,
    }
