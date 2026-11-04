from helpers.agent_api import (
    build_agent_responses_invoke,
    build_create_agent_body,
    build_update_agent_body,
)


def test_build_create_agent_body_wraps_definition() -> None:
    body = build_create_agent_body(
        name="my-agent",
        model="gpt-4.1",
        instructions="Be helpful",
        metadata={"team": "platform"},
    )
    assert body["name"] == "my-agent"
    assert body["definition"] == {
        "kind": "prompt",
        "model": "gpt-4.1",
        "instructions": "Be helpful",
    }
    assert body["metadata"] == {"team": "platform"}


def test_build_update_agent_body_nested_definition() -> None:
    body = build_update_agent_body(instructions="New text", model="gpt-5")
    assert body["definition"] == {
        "model": "gpt-5",
        "instructions": "New text",
    }


def test_build_agent_responses_invoke_uses_protocol_path() -> None:
    path, params, body = build_agent_responses_invoke(
        agent_id="Omby-agent",
        user_input="hello",
        conversation_id="conv_123",
    )
    assert path == "agents/Omby-agent/endpoint/protocols/openai/responses"
    assert params == {}
    assert body["input"] == "hello"
    assert body["conversation"] == "conv_123"
