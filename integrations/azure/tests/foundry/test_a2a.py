from azure_integration.foundry.helpers.a2a import (
    a2a_connection_ids_from_tools,
    connection_name_from_ref,
    parse_foundry_a2a_url,
    skill_names_from_refs,
)

_A2A_URL = (
    "https://acct.services.ai.azure.com/api/projects/demo-proj/agents/"
    "my-agent/endpoint/protocols/a2a"
)
_ARM_CONN = (
    "/subscriptions/s/resourceGroups/rg/providers/Microsoft.CognitiveServices/"
    "accounts/acct/projects/proj/connections/hosted-basic-responses-a2a"
)


def test_a2a_helpers() -> None:
    project, agent = parse_foundry_a2a_url(_A2A_URL)
    assert project == "demo-proj" and agent == "my-agent"
    assert parse_foundry_a2a_url("https://example.com/mcp") == (None, None)
    assert skill_names_from_refs(["alpha", {"name": "beta"}, {"id": "gamma"}]) == [
        "alpha",
        "beta",
        "gamma",
    ]
    assert connection_name_from_ref("conn-a") == "conn-a"
    assert connection_name_from_ref(_ARM_CONN) == "hosted-basic-responses-a2a"
    tools = [
        {"type": "a2a", "project_connection_id": "conn-a"},
        {"type": "a2a_preview", "projectConnectionId": "conn-b"},
        {"type": "mcp", "project_connection_id": "ignored"},
        {"type": "a2a", "project_connection_id": "conn-a"},
        {"type": "a2a", "project_connection_id": _ARM_CONN},
    ]
    assert a2a_connection_ids_from_tools(tools) == [
        "conn-a",
        "conn-b",
        "hosted-basic-responses-a2a",
    ]
