from typing import Any

from pytest_httpx import HTTPXMock

from client import ScaleQualityClient


def test_client_sets_bearer_auth_header(mock_ocean_context: None) -> None:
    client = ScaleQualityClient(
        base_url="https://app.scalequality.io/v1", api_key="sq_live_test"
    )
    assert client.http_client.headers["Authorization"] == "Bearer sq_live_test"
    assert client.base_url == "https://app.scalequality.io/v1"


def test_client_strips_trailing_slash_from_base_url(mock_ocean_context: None) -> None:
    client = ScaleQualityClient(
        base_url="https://app.scalequality.io/v1/", api_key="sq_live_test"
    )
    assert client.base_url == "https://app.scalequality.io/v1"


async def test_get_entities_returns_the_entities_array(
    mock_ocean_context: None, httpx_mock: HTTPXMock
) -> None:
    sample: dict[str, Any] = {
        "orgId": "org-1",
        "count": 1,
        "entities": [
            {
                "subject": {"type": "org", "id": "org-1", "name": "Acme"},
                "measuredAt": "2026-07-22T00:00:00.000Z",
                "signals": {
                    "durability": {
                        "value": 72,
                        "status": "warn",
                        "deepLinkUrl": "https://app.scalequality.io/ai-governance",
                    },
                    "engMaturity": {"value": 3},
                    "codeMaturity": {"value": 52},
                    "techRadar": {"value": 76},
                },
            }
        ],
    }
    httpx_mock.add_response(url="https://app.scalequality.io/v1/entities", json=sample)

    client = ScaleQualityClient(
        base_url="https://app.scalequality.io/v1", api_key="sq_live_test"
    )
    batches = [batch async for batch in client.get_entities()]
    entities = [entity for batch in batches for entity in batch]

    assert len(batches) == 1
    assert len(entities) == 1
    assert entities[0]["subject"]["id"] == "org-1"
    assert entities[0]["signals"]["durability"]["value"] == 72


async def test_get_entities_handles_empty_payload(
    mock_ocean_context: None, httpx_mock: HTTPXMock
) -> None:
    httpx_mock.add_response(
        url="https://app.scalequality.io/v1/entities",
        json={"orgId": "org-1", "count": 0, "entities": []},
    )

    client = ScaleQualityClient(
        base_url="https://app.scalequality.io/v1", api_key="sq_live_test"
    )
    entities = [entity async for batch in client.get_entities() for entity in batch]

    assert entities == []
