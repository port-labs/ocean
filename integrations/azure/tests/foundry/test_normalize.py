from azure_integration.foundry.core.exporters.agents_exporter import (
    _version_with_identity,
)
from azure_integration.foundry.helpers.responses_catalog import (
    conversation_row_from_response,
    count_tool_calls_in_response,
    merge_usage_into_row,
)


def test_version_with_identity() -> None:
    normalized = _version_with_identity(
        {
            "version": "6",
            "status": "active",
            "definition": {"kind": "prompt", "model": "gpt-5"},
            "instance_identity": {"principal_id": "p1"},
        },
        "Omby-agent",
    )
    assert normalized["id"] == "Omby-agent/6"
    assert normalized["agent_id"] == "Omby-agent"
    assert normalized["definition"]["kind"] == "prompt"
    assert normalized["instance_identity"]["principal_id"] == "p1"


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
