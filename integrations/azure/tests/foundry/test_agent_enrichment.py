from azure_integration.foundry.helpers.agent_enrichment import (
    enrich_agent_row,
    foundry_portal_agent_url,
)

_ARM = (
    "/subscriptions/sub-1/resourceGroups/rg/providers/"
    "Microsoft.CognitiveServices/accounts/acct/projects/demo"
)
_PORTAL_ARM = (
    "/subscriptions/11e43792-2b16-4f94-b5ea-de10eade3aef/resourceGroups/rg-demo/"
    "providers/Microsoft.CognitiveServices/accounts/acct-demo/projects/demo"
)


def test_enrich_agent_row_adds_project_and_portal_url() -> None:
    agent = {
        "id": "agent-1",
        "name": "MyAgent",
        "versions": {"latest": {"version": "3"}},
    }
    row = enrich_agent_row(
        agent,
        project_endpoint="https://acct.services.ai.azure.com/api/projects/demo",
        project_id=_ARM,
    )
    assert row["__foundryProjectId"] == _ARM
    assert row["__foundryPortalAgentUrl"] is not None
    assert "/build/agents/MyAgent/build?version=3" in row["__foundryPortalAgentUrl"]


def test_foundry_portal_agent_url() -> None:
    url = foundry_portal_agent_url(_PORTAL_ARM, "TESTONE", version="8")
    assert url is not None
    assert "/build/agents/TESTONE/build?version=8" in url
    assert "EeQ3kisWT5S16t4Q6t467w,rg-demo,,acct-demo,demo" in url
