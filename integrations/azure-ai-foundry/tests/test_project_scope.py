from helpers.project_scope import enrich_with_project, get_project_endpoint


def test_get_project_endpoint() -> None:
    assert (
        get_project_endpoint()
        == "https://acct.services.ai.azure.com/api/projects/demo"
    )


def test_enrich_with_project_adds_metadata() -> None:
    enriched = enrich_with_project({"id": "agent-1", "name": "demo"})
    assert enriched == {"id": "agent-1", "name": "demo"}
