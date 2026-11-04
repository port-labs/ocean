from clients.http.foundry_client import FoundryHttpClient


def test_items_from_payload_data_key() -> None:
    payload = {"data": [{"id": "1"}, {"id": "2"}]}
    assert len(FoundryHttpClient.items_from_payload(payload)) == 2


def test_items_from_payload_list() -> None:
    payload = [{"id": "a"}]
    assert FoundryHttpClient.items_from_payload(payload)[0]["id"] == "a"


def test_openai_routes_skip_api_version() -> None:
    url = "https://x.services.ai.azure.com/api/projects/p/openai/v1/conversations"
    assert FoundryHttpClient.uses_openai_compatible_routes(url) is True
    assert (
        FoundryHttpClient.uses_openai_compatible_routes(
            "https://x.services.ai.azure.com/api/projects/p/agents"
        )
        is False
    )
    assert (
        FoundryHttpClient.uses_openai_compatible_routes(
            "https://x.services.ai.azure.com/api/projects/p/agents/a/endpoint/protocols/openai/responses"
        )
        is False
    )
