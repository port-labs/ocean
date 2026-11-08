from azure_integration.foundry.helpers.responses_catalog import agent_id_from_response, normalize_foundry_response


def test_agent_id_from_response_agent_dict() -> None:
    assert (
        agent_id_from_response({"agent": {"name": "Omby-agent:6"}}) == "Omby-agent"
    )


def test_normalize_foundry_response_flat_list_fields() -> None:
    row = normalize_foundry_response(
        {
            "id": "resp_list",
            "conversation_id": "conv_1",
            "status": "completed",
            "created_at": "2026-11-05T09:49:58+00:00",
            "prompt_tokens": 8,
            "completion_tokens": 10,
            "total_tokens": 18,
            "model_deployment_id": "gpt-4o-mini",
        }
    )
    assert row is not None
    assert row["prompt_tokens"] == 8
    assert row["model_deployment_id"] == "gpt-4o-mini"
    assert "tool_call_count" not in row


def test_normalize_foundry_response() -> None:
    row = normalize_foundry_response(
        {
            "id": "resp_1",
            "status": "completed",
            "created_at": "1793724875",
            "conversation": {"id": "conv_1"},
            "model": "gpt-4.1",
            "agent": {"name": "Omby-agent"},
            "usage": {"input_tokens": 1, "output_tokens": 2, "total_tokens": 3},
            "output": [{"type": "function_call", "name": "x"}],
        }
    )
    assert row is not None
    assert row["id"] == "resp_1"
    assert row["conversation_id"] == "conv_1"
    assert row["model_deployment_id"] == "gpt-4.1"
    assert row["agent_id"] == "Omby-agent"
    assert row["prompt_tokens"] == 1
    assert row["tool_call_count"] == 1
