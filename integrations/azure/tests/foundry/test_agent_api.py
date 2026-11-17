from typing import Any

import pytest

from azure_integration.foundry.actions.create_agent_executor import CreateAgentInputs
from azure_integration.foundry.actions.update_agent_executor import UpdateAgentInputs
from azure_integration.foundry.helpers.agent_api import (
    foundry_features_header,
    latest_agent_definition,
)

_ENDPOINT = "https://example.services.ai.azure.com/api/projects/p1"


def test_create_agent_to_api_body_wraps_definition() -> None:
    body = CreateAgentInputs(
        projectEndpoint=_ENDPOINT,
        name="my-agent",
        model="gpt-4.1",
        instructions="Be helpful",
    ).to_api_body()
    assert body["name"] == "my-agent"
    assert body["definition"] == {
        "kind": "prompt",
        "model": "gpt-4.1",
        "instructions": "Be helpful",
    }


def test_create_agent_to_api_body_skips_prompt_fields_for_hosted() -> None:
    body = CreateAgentInputs(
        projectEndpoint=_ENDPOINT,
        name="hosted-agent",
        model="ignored",
        instructions="ignored",
        config={"definition": {"kind": "hosted", "cpu": "1"}},
    ).to_api_body()
    assert body["definition"] == {"kind": "hosted", "cpu": "1"}
    assert "model" not in body["definition"]
    assert "instructions" not in body["definition"]


def test_create_agent_to_api_body_merges_config_under_first_class() -> None:
    body = CreateAgentInputs(
        projectEndpoint=_ENDPOINT,
        name="my-agent",
        model="gpt-4.1",
        instructions="Be helpful",
        config={
            "name": "ignored",
            "description": "ops agent",
            "metadata": {"team": "platform"},
            "definition": {
                "kind": "prompt",
                "model": "should-lose",
                "tools": [
                    {
                        "type": "mcp",
                        "server_label": "github",
                        "server_url": "https://example",
                    }
                ],
            },
        },
    ).to_api_body()
    assert body["name"] == "my-agent"
    assert body["description"] == "ops agent"
    assert body["metadata"] == {"team": "platform"}
    assert body["definition"]["model"] == "gpt-4.1"
    assert body["definition"]["instructions"] == "Be helpful"
    assert body["definition"]["tools"] == [
        {
            "type": "mcp",
            "server_label": "github",
            "server_url": "https://example",
        }
    ]


def test_update_agent_to_api_body_nested_definition() -> None:
    body = UpdateAgentInputs(
        projectEndpoint=_ENDPOINT,
        agentId="agent-1",
        instructions="New text",
        model="gpt-5",
    ).to_api_body()
    assert body["definition"] == {
        "model": "gpt-5",
        "instructions": "New text",
    }


def test_update_agent_to_api_body_merges_config_tools() -> None:
    body = UpdateAgentInputs(
        projectEndpoint=_ENDPOINT,
        agentId="agent-1",
        instructions="New text",
        config={
            "definition": {
                "tools": [{"type": "function", "name": "lookup"}],
            },
            "description": "updated",
        },
    ).to_api_body()
    assert body["description"] == "updated"
    assert body["definition"] == {
        "tools": [{"type": "function", "name": "lookup"}],
        "instructions": "New text",
    }


def test_update_agent_to_api_body_does_not_force_prompt_kind() -> None:
    body = UpdateAgentInputs(
        projectEndpoint=_ENDPOINT,
        agentId="agent-1",
        config={"definition": {"kind": "hosted", "cpu": "1"}},
    ).to_api_body()
    assert body["definition"]["kind"] == "hosted"


@pytest.mark.parametrize(
    ("agent", "expected"),
    [
        (
            {
                "definition": {"kind": "prompt", "model": "old"},
                "versions": {
                    "latest": {
                        "definition": {
                            "kind": "prompt",
                            "model": "gpt-5",
                            "instructions": "hi",
                        }
                    }
                },
            },
            {"kind": "prompt", "model": "gpt-5", "instructions": "hi"},
        ),
        (
            {"definition": {"kind": "prompt", "model": "gpt-4.1"}},
            {"kind": "prompt", "model": "gpt-4.1"},
        ),
    ],
)
def test_latest_agent_definition(
    agent: dict[str, Any], expected: dict[str, Any]
) -> None:
    assert latest_agent_definition(agent) == expected


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        ("prompt", None),
        ("hosted", {"Foundry-Features": "HostedAgents=V1Preview"}),
        ("workflow", {"Foundry-Features": "WorkflowAgents=V1Preview"}),
        ("external", {"Foundry-Features": "ExternalAgents=V1Preview"}),
        ("voice", {"Foundry-Features": "VoiceAgents=V1Preview"}),
    ],
)
def test_foundry_features_header(kind: str, expected: dict[str, str] | None) -> None:
    assert foundry_features_header(kind) == expected
