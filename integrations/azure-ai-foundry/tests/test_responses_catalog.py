from helpers.responses_catalog import agent_id_from_response, normalize_foundry_response


def test_agent_id_from_response_agent_dict() -> None:
    assert (
        agent_id_from_response({"agent": {"name": "Omby-agent:6"}}) == "Omby-agent"
    )


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
