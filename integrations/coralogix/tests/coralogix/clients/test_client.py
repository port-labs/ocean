from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from coralogix.clients.client import CoralogixClient, PaginationStyle
from coralogix.helpers.exceptions import CoralogixApiError, CoralogixAuthenticationError
from coralogix.helpers.utils import IgnoredError

BASE = "https://api.eu2.coralogix.com"


def _response(status: int, body: Any = None) -> httpx.Response:
    return httpx.Response(
        status,
        json=body if body is not None else {},
        request=httpx.Request("GET", BASE),
    )


def _client(*responses: httpx.Response) -> tuple[CoralogixClient, AsyncMock]:
    client = CoralogixClient(base_url=BASE, api_key="k")
    request = AsyncMock(side_effect=list(responses))
    client.http_client = MagicMock(request=request)
    return client, request


async def test_send_api_request_builds_url_and_auth() -> None:
    client, request = _client(_response(200, {"slos": []}))
    assert await client.send_api_request("/mgmt/openapi/5/slo/slos/v1") == {"slos": []}
    kwargs = request.call_args.kwargs
    assert kwargs["url"] == f"{BASE}/mgmt/openapi/5/slo/slos/v1"
    assert kwargs["headers"] == {
        "Authorization": "Bearer k",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }


@pytest.mark.parametrize("status", [403, 404])
async def test_send_api_request_fails_on_permission_and_missing(status: int) -> None:
    client, _ = _client(_response(status, {"code": status}))
    with pytest.raises(CoralogixApiError):
        await client.send_api_request("mgmt/openapi/5/cases/cases/v1")


async def test_send_api_request_can_ignore_a_missing_resource() -> None:
    client, _ = _client(_response(404, {"code": 404}))
    assert (
        await client.send_api_request(
            "mgmt/openapi/5/slo/slos/v1/missing",
            ignored_errors=[IgnoredError(status=404, message="resource not found")],
        )
        == {}
    )


async def test_send_api_request_rejects_non_object_json() -> None:
    client, _ = _client(_response(200, ["not", "an", "object"]))
    with pytest.raises(CoralogixApiError):
        await client.send_api_request("mgmt/openapi/5/slo/slos/v1")


async def test_send_api_request_raises_clear_error_on_401() -> None:
    client, _ = _client(_response(401))
    with pytest.raises(CoralogixAuthenticationError):
        await client.send_api_request("mgmt/openapi/5/slo/slos/v1")


async def test_send_api_request_raises_on_500() -> None:
    client, _ = _client(_response(500, {"message": "boom"}))
    with pytest.raises(httpx.HTTPStatusError):
        await client.send_api_request("mgmt/openapi/5/slo/slos/v1")


async def test_token_query_pagination_follows_next_page_token() -> None:
    client, request = _client(
        _response(
            200, {"alertDefs": [{"id": "1"}], "pagination": {"nextPageToken": "t2"}}
        ),
        _response(
            200, {"alertDefs": [{"id": "2"}], "pagination": {"nextPageToken": ""}}
        ),
    )
    pages = [
        page
        async for page in client.send_paginated_request(
            "alerts",
            data_key="alertDefs",
            style=PaginationStyle.TOKEN_QUERY,
            page_size=1,
        )
    ]
    assert pages == [[{"id": "1"}], [{"id": "2"}]]
    first, second = (call.kwargs["params"] for call in request.call_args_list)
    assert first == {"pagination.pageSize": 1}
    assert second == {"pagination.pageSize": 1, "pagination.pageToken": "t2"}


async def test_token_body_pagination_keeps_filters_in_body() -> None:
    client, request = _client(
        _response(200, {"cases": [{"id": "a"}], "pagination": {"nextPageToken": "n"}}),
        _response(200, {"cases": [], "pagination": {}}),
    )
    pages = [
        page
        async for page in client.send_paginated_request(
            "cases",
            data_key="cases",
            style=PaginationStyle.TOKEN_BODY,
            method="POST",
            json_data={"filters": {"statuses": ["CASE_STATUS_ACTIVE"]}},
            page_size=50,
        )
    ]
    assert pages == [[{"id": "a"}]]
    bodies = [call.kwargs["json"] for call in request.call_args_list]
    assert bodies[0] == {
        "filters": {"statuses": ["CASE_STATUS_ACTIVE"]},
        "pagination": {"pageSize": 50},
    }
    assert bodies[1]["pagination"] == {"pageSize": 50, "pageToken": "n"}


async def test_pagination_fails_when_page_token_repeats() -> None:
    client, _ = _client(
        _response(
            200, {"alertDefs": [{"id": "1"}], "pagination": {"nextPageToken": "t"}}
        ),
        _response(
            200, {"alertDefs": [{"id": "1"}], "pagination": {"nextPageToken": "t"}}
        ),
    )
    with pytest.raises(CoralogixApiError, match="repeated a page token"):
        async for _page in client.send_paginated_request(
            "alerts",
            data_key="alertDefs",
            style=PaginationStyle.TOKEN_QUERY,
            page_size=1,
        ):
            pass


async def test_pagination_fails_when_page_cap_is_hit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("coralogix.clients.client.MAX_PAGES", 1)
    client, request = _client(
        _response(
            200, {"alertDefs": [{"id": "1"}], "pagination": {"nextPageToken": "t2"}}
        ),
        _response(
            200, {"alertDefs": [{"id": "2"}], "pagination": {"nextPageToken": ""}}
        ),
    )
    with pytest.raises(CoralogixApiError, match="after 1 pages"):
        async for _page in client.send_paginated_request(
            "alerts",
            data_key="alertDefs",
            style=PaginationStyle.TOKEN_QUERY,
            page_size=1,
        ):
            pass
    assert request.call_count == 1


async def test_pagination_fails_when_endpoint_forbidden() -> None:
    client, request = _client(_response(403, {"code": 403}))
    with pytest.raises(CoralogixApiError):
        async for _page in client.send_paginated_request(
            "mgmt/openapi/5/cases/cases/v1",
            data_key="cases",
            style=PaginationStyle.TOKEN_BODY,
            method="POST",
        ):
            pass
    assert request.call_count == 1
