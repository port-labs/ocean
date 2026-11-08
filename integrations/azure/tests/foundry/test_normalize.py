from azure_integration.foundry.core.exporters.agent_versions_exporter import (
    _normalize_agent_version,
)
from azure_integration.foundry.core.exporters.agents_exporter import _normalize_agent
from azure_integration.foundry.core.exporters.conversations_exporter import (
    _normalize_conversation,
)
from azure_integration.foundry.core.exporters.model_deployments_exporter import (
    _normalize_deployment,
)
from azure_integration.foundry.helpers.conversation_catalog import (
    conversation_row_from_response,
)
from azure_integration.foundry.helpers.usage_metrics import (
    count_tool_calls_in_response,
    merge_usage_into_row,
)


def test_normalize_agent_flattens_latest_definition() -> None:
    raw = {
        "id": "Omby-agent",
        "name": "Omby-agent",
        "state": "enabled",
        "versions": {
            "latest": {
                "created_at": 1_700_000_000,
                "definition": {
                    "kind": "prompt",
                    "model": "gpt-5",
                    "instructions": "be helpful",
                    "tools": [{}, {}],
                },
                "version": "6",
                "status": "active",
                "agent_guid": "6a0d6833-de7e-49a4-9d7f-973aa96facb1",
            }
        },
        "configuration_state": "enabled",
    }
    normalized = _normalize_agent(raw)
    assert normalized["kind"] == "prompt"
    assert normalized["model"] == "gpt-5"
    assert normalized["instructions"] == "be helpful"
    assert normalized["status"] == "enabled"
    assert normalized["version"] == "6"
    assert normalized["version_status"] == "active"
    assert normalized["configuration_state"] == "enabled"
    assert normalized["tool_count"] == 2
    assert normalized["source_platform"] == "Azure AI Foundry"
    assert str(normalized["created_at"]).endswith("+00:00")


def test_normalize_agent_version() -> None:
    normalized = _normalize_agent_version(
        {
            "version": "6",
            "status": "active",
            "description": "v6",
            "definition": {"kind": "prompt", "model": "gpt-5", "tools": [{}]},
            "instance_identity": {"principal_id": "p1", "client_id": "c1"},
            "created_at": 1_700_000_000,
        },
        "Omby-agent",
    )
    assert normalized["id"] == "Omby-agent/6"
    assert normalized["agent_id"] == "Omby-agent"
    assert normalized["entra_principal_id"] == "p1"


def test_normalize_deployment_uses_model_name() -> None:
    raw = {
        "name": "gpt-5",
        "type": "ModelDeployment",
        "modelName": "gpt-5",
        "modelVersion": "2025-08-07",
        "modelPublisher": "OpenAI",
        "capabilities": {"chat_completion": "true"},
        "sku": {"name": "GlobalStandard"},
    }
    normalized = _normalize_deployment(raw)
    assert normalized["id"] == "gpt-5"
    assert normalized["model"] == "gpt-5"
    assert normalized["sku"] == "GlobalStandard"
    assert normalized["deployment_type"] == "ModelDeployment"
    assert normalized["model_version"] == "2025-08-07"
    assert normalized["model_publisher"] == "OpenAI"


def test_conversation_row_from_response() -> None:
    row = conversation_row_from_response(
        {
            "id": "resp_1",
            "conversation": {"id": "conv_abc"},
            "usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 15},
            "output": [{"type": "mcp_call", "id": "c1"}],
        },
        agent_id="Omby-agent:8",
    )
    assert row is not None
    assert row["id"] == "conv_abc"
    assert row["participant_agent_ids"] == ["Omby-agent"]
    assert row["prompt_tokens"] == 10
    assert row["completion_tokens"] == 5
    assert row["total_tokens"] == 15
    assert row["tool_call_count"] == 1


def test_normalize_conversation_maps_created_at_and_metadata() -> None:
    normalized = _normalize_conversation(
        {
            "id": "conv_abc",
            "created_at": 1_700_000_000,
            "metadata": {"team": "platform"},
            "participant_agent_ids": ["Omby-agent"],
        }
    )
    assert normalized["id"] == "conv_abc"
    assert normalized["participant_agent_ids"] == ["Omby-agent"]
    assert str(normalized["created_at"]).endswith("+00:00")
    assert normalized["metadata"] == {"team": "platform"}


def test_merge_usage_into_row() -> None:
    row: dict[str, object] = {}
    merge_usage_into_row(row, {"input_tokens": 3, "output_tokens": 2})
    assert row["prompt_tokens"] == 3
    assert row["completion_tokens"] == 2
    assert row["total_tokens"] == 5


def test_count_tool_calls_in_response() -> None:
    assert (
        count_tool_calls_in_response(
            {"output": [{"type": "message"}, {"type": "function_call"}]}
        )
        == 1
    )
