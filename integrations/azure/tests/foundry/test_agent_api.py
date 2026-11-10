from azure_integration.foundry.helpers.agent_api import (
    build_create_agent_body,
    build_update_agent_body,
)


def test_build_create_agent_body_wraps_definition() -> None:
    body = build_create_agent_body(
        name="my-agent",
        model="gpt-4.1",
        instructions="Be helpful",
    )
    assert body["name"] == "my-agent"
    assert body["definition"] == {
        "kind": "prompt",
        "model": "gpt-4.1",
        "instructions": "Be helpful",
    }


def test_build_create_agent_body_merges_config_under_first_class() -> None:
    body = build_create_agent_body(
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
    )
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


def test_build_update_agent_body_nested_definition() -> None:
    body = build_update_agent_body(instructions="New text", model="gpt-5")
    assert body["definition"] == {
        "model": "gpt-5",
        "instructions": "New text",
    }


def test_build_update_agent_body_merges_config_tools() -> None:
    body = build_update_agent_body(
        instructions="New text",
        config={
            "definition": {
                "tools": [{"type": "function", "name": "lookup"}],
            },
            "description": "updated",
        },
    )
    assert body["description"] == "updated"
    assert body["definition"] == {
        "tools": [{"type": "function", "name": "lookup"}],
        "instructions": "New text",
    }
