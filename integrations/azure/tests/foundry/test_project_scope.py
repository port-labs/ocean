from azure_integration.foundry.helpers.project_scope import (
    enrich_with_project,
    get_project_endpoint,
    project_name_from_endpoint,
)


def test_get_project_endpoint() -> None:
    assert (
        get_project_endpoint()
        == "https://acct.services.ai.azure.com/api/projects/demo"
    )


def test_project_name_from_endpoint() -> None:
    assert (
        project_name_from_endpoint(
            "https://acct.services.ai.azure.com/api/projects/proj-default"
        )
        == "proj-default"
    )


def test_enrich_with_project_adds_metadata() -> None:
    enriched = enrich_with_project({"id": "agent-1", "name": "demo"})
    assert enriched["id"] == "agent-1"
    assert enriched["name"] == "demo"
    assert (
        enriched["foundryProjectEndpoint"]
        == "https://acct.services.ai.azure.com/api/projects/demo"
    )
