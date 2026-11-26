from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from incident_io.clients.client import IncidentIoClient
from incident_io.helpers.exceptions import (
    IncidentIoApiError,
    IncidentIoAuthenticationError,
)

BASE = "https://api.incident.io"


def _response(status: int, body: Any = None) -> httpx.Response:
    return httpx.Response(
        status,
        json=body if body is not None else {},
        request=httpx.Request("GET", BASE),
    )


def _client(*responses: httpx.Response) -> tuple[IncidentIoClient, AsyncMock]:
    client = IncidentIoClient(base_url=BASE, api_key="inc_test")
    request = AsyncMock(side_effect=list(responses))
    client._http_client = MagicMock(request=request)
    return client, request


async def test_send_api_request_builds_url_and_auth() -> None:
    client, request = _client(_response(200, {"incidents": []}))
    assert await client.send_api_request("v2/incidents") == {"incidents": []}
    kwargs = request.call_args.kwargs
    assert kwargs["url"] == f"{BASE}/v2/incidents"
    assert kwargs["headers"]["Authorization"] == "Bearer inc_test"
    assert kwargs["headers"]["Accept"] == "application/json"
    assert "Content-Type" not in kwargs["headers"]


@pytest.mark.parametrize("status", [403, 404])
async def test_send_api_request_fails_on_permission_and_missing(status: int) -> None:
    client, _ = _client(_response(status, {"type": "error", "status": status}))
    with pytest.raises(IncidentIoApiError):
        await client.send_api_request("v2/schedules")


async def test_send_api_request_names_the_missing_scope() -> None:
    client, _ = _client(_response(403, {"status": 403}))
    with pytest.raises(IncidentIoApiError, match="users.view"):
        await client.send_api_request("v2/users")


async def test_send_api_request_rejects_non_object_json() -> None:
    client, _ = _client(_response(200, ["not", "an", "object"]))
    with pytest.raises(IncidentIoApiError):
        await client.send_api_request("v2/incidents")


async def test_send_api_request_raises_clear_error_on_401() -> None:
    client, _ = _client(_response(401))
    with pytest.raises(IncidentIoAuthenticationError):
        await client.send_api_request("v2/incidents")


async def test_send_api_request_raises_on_500() -> None:
    client, _ = _client(_response(500, {"message": "boom"}))
    with pytest.raises(httpx.HTTPStatusError):
        await client.send_api_request("v2/users")


def test_repeated_filter_params_encode() -> None:
    encoded = str(httpx.QueryParams({"status_category[one_of]": ["live", "closed"]}))
    assert encoded.count("status_category") == 2
    assert "live" in encoded and "closed" in encoded


async def test_pagination_follows_after_then_stops_on_empty_page() -> None:
    client, request = _client(
        _response(
            200,
            {
                "incidents": [{"id": "a"}],
                "pagination_meta": {"after": "a", "page_size": 1},
            },
        ),
        _response(
            200,
            {"incidents": [], "pagination_meta": {"page_size": 1}},
        ),
    )
    pages = [
        page
        async for page in client.send_paginated_request(
            "v2/incidents", data_key="incidents", page_size=1
        )
    ]
    assert pages == [[{"id": "a"}]]
    first, second = (call.kwargs["params"] for call in request.call_args_list)
    assert first == {"page_size": 1}
    assert second == {"page_size": 1, "after": "a"}


async def test_pagination_keeps_filters() -> None:
    client, request = _client(
        _response(
            200, {"incidents": [{"id": "a"}], "pagination_meta": {"page_size": 1}}
        )
    )
    pages = [
        page
        async for page in client.send_paginated_request(
            "v2/incidents",
            data_key="incidents",
            params={"created_at[gte]": "2024-01-01"},
            page_size=50,
        )
    ]
    assert pages == [[{"id": "a"}]]
    assert request.call_args.kwargs["params"] == {
        "created_at[gte]": "2024-01-01",
        "page_size": 50,
    }


async def test_pagination_fails_when_page_token_repeats() -> None:
    client, _ = _client(
        _response(
            200,
            {"incidents": [{"id": "a"}], "pagination_meta": {"after": "t"}},
        ),
        _response(
            200,
            {"incidents": [{"id": "a"}], "pagination_meta": {"after": "t"}},
        ),
    )
    with pytest.raises(IncidentIoApiError, match="repeated a page token"):
        async for _page in client.send_paginated_request(
            "v2/incidents", data_key="incidents", page_size=1
        ):
            pass


async def test_pagination_fails_when_page_cap_is_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("incident_io.clients.client.MAX_PAGES", 1)
    client, _ = _client(
        _response(
            200,
            {"incidents": [{"id": "a"}], "pagination_meta": {"after": "t2"}},
        ),
        _response(200, {"incidents": [], "pagination_meta": {}}),
    )
    with pytest.raises(IncidentIoApiError, match="after 1 pages"):
        async for _page in client.send_paginated_request(
            "v2/incidents", data_key="incidents", page_size=1
        ):
            pass


async def test_pagination_fails_when_data_key_is_missing() -> None:
    client, _ = _client(_response(200, {"pagination_meta": {}}))
    with pytest.raises(IncidentIoApiError, match="did not include 'incidents'"):
        async for _page in client.send_paginated_request(
            "v2/incidents", data_key="incidents"
        ):
            pass
