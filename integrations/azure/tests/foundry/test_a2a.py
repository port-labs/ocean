from azure_integration.foundry.helpers.a2a import (
    a2a_connection_ids_from_tools,
    parse_foundry_a2a_url,
    skill_names_from_refs,
)

_A2A_URL = (
    "https://acct.services.ai.azure.com/api/projects/demo-proj/agents/"
    "my-agent/endpoint/protocols/a2a"
)


def test_parse_foundry_a2a_url_extracts_project_and_agent() -> None:
    project, agent = parse_foundry_a2a_url(_A2A_URL)
    assert project == "demo-proj"
    assert agent == "my-agent"


def test_parse_foundry_a2a_url_non_foundry_target() -> None:
    assert parse_foundry_a2a_url("https://example.com/mcp") == (None, None)


def test_skill_names_from_refs() -> None:
    assert skill_names_from_refs(["alpha", {"name": "beta"}, {"id": "gamma"}]) == [
        "alpha",
        "beta",
        "gamma",
    ]


def test_a2a_connection_ids_from_tools_dedupes() -> None:
    tools = [
        {"type": "a2a", "project_connection_id": "conn-a"},
        {"type": "a2a_preview", "projectConnectionId": "conn-b"},
        {"type": "mcp", "project_connection_id": "ignored"},
        {"type": "a2a", "project_connection_id": "conn-a"},
    ]
    assert a2a_connection_ids_from_tools(tools) == ["conn-a", "conn-b"]
