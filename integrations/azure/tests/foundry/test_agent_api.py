from typing import Any

import pytest

from azure_integration.foundry.actions.create_agent_executor import CreateAgentInputs
from azure_integration.foundry.actions.invoke_agent_executor import InvokeAgentInputs
from azure_integration.foundry.actions.update_agent_executor import UpdateAgentInputs
from azure_integration.foundry.models.agent import (
    Agent,
    HostedAgentDefinition,
    PromptAgentDefinition,
    features_header_for_kind,
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


def test_prompt_agent_from_foundry_get() -> None:
    agent = Agent.model_validate(
        {
            "object": "agent",
            "id": "helpful-agent",
            "versions": {
                "latest": {
                    "definition": {
                        "kind": "prompt",
                        "model": "gpt-4o-mini",
                        "instructions": "Be helpful",
                        "tools": [
                            {
                                "type": "mcp",
                                "server_label": "tb",
                                "server_url": "https://x/toolboxes/tb/versions/2/mcp",
                            }
                        ],
                    }
                }
            },
            "__foundryProjectEndpoint": "https://x/api/projects/p",
        }
    )
    assert agent.kind == "prompt"
    assert isinstance(agent.latest_definition, PromptAgentDefinition)
    assert agent.latest_definition.model == "gpt-4o-mini"
    assert len(agent.latest_definition.tools) == 1
    assert agent.latest_definition.tools[0]["server_label"] == "tb"


def test_hosted_agent_from_foundry_get() -> None:
    agent = Agent.model_validate(
        {
            "object": "agent",
            "id": "hosted-1",
            "versions": {
                "latest": {
                    "definition": {
                        "kind": "hosted",
                        "cpu": "0.5",
                        "memory": "1Gi",
                        "environment_variables": {"FOO": "bar"},
                    }
                }
            },
            "__foundryProjectId": "/subscriptions/.../projects/p",
        }
    )
    assert agent.kind == "hosted"
    assert isinstance(agent.latest_definition, HostedAgentDefinition)
    dumped = agent.latest_definition.model_dump()
    assert dumped["cpu"] == "0.5"
    assert dumped["memory"] == "1Gi"
    assert "tools" not in dumped


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
def test_features_header(kind: str, expected: dict[str, str] | None) -> None:
    assert features_header_for_kind(kind) == expected


def test_build_responses_invoke_uses_protocol_path() -> None:
    inputs = InvokeAgentInputs(
        projectArmId=(
            "/subscriptions/s/resourceGroups/rg/providers/"
            "Microsoft.CognitiveServices/accounts/acct/projects/p"
        ),
        agentId="Omby-agent",
        input="hello",
    )
    path, body = inputs.build_responses_invoke("conv_123")
    assert path == "agents/Omby-agent/endpoint/protocols/openai/responses"
    assert body["input"] == "hello"
    assert body["conversation"] == "conv_123"
