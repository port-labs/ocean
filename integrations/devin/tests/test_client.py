from typing import Any
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from clients.devin_client import DevinClient
from clients.exceptions import DevinPaginationError
from core.sessions import DevinSessions
from tests.fakes import http_error


def _response(status: int, payload: Any = None) -> httpx.Response:
    request = httpx.Request("GET", "https://api.devin.ai")
    if payload is None:
        return httpx.Response(status, request=request)
    return httpx.Response(status, request=request, json=payload)


@pytest.fixture
def request_mock() -> AsyncMock:
    return AsyncMock(return_value=_response(200, {}))


@pytest.fixture
def client(request_mock: AsyncMock) -> DevinClient:
    instance = DevinClient(
        api_host="https://api.devin.ai/", api_key="cog_test", org_id="org-1"
    )
    instance._client = MagicMock()
    instance._client.request = request_mock
    return instance


def _last_kwargs(mock: AsyncMock) -> dict[str, Any]:
    assert mock.await_args is not None
    return dict(mock.await_args.kwargs)


async def test_requests_are_org_scoped_with_bearer_auth_and_retryable(
    client: DevinClient, request_mock: AsyncMock
) -> None:
    await client.send_api_request("GET", "/sessions/devin-1")

    kwargs = _last_kwargs(request_mock)
    assert (
        kwargs["url"] == "https://api.devin.ai/v3/organizations/org-1/sessions/devin-1"
    )
    assert kwargs["headers"]["Authorization"] == "Bearer cog_test"
    assert kwargs["extensions"] == {"retryable": True}


async def test_absolute_paths_skip_the_org_prefix(
    client: DevinClient, request_mock: AsyncMock
) -> None:
    await client.send_api_request(
        "GET", "/v3beta1/organizations/org-1/members/users", absolute_path=True
    )

    url = _last_kwargs(request_mock)["url"]
    assert url == "https://api.devin.ai/v3beta1/organizations/org-1/members/users"


async def test_none_params_are_dropped(
    client: DevinClient, request_mock: AsyncMock
) -> None:
    await client.send_api_request(
        "GET", "/sessions", params={"tags": ["a", "b"], "playbook_id": None}
    )

    assert _last_kwargs(request_mock)["params"] == {"tags": ["a", "b"]}


async def test_list_params_are_serialized_as_repeated_keys() -> None:
    request = httpx.Request(
        "GET", "https://api.devin.ai/x", params={"tags": ["a", "b"], "first": 1}
    )
    assert str(request.url) == "https://api.devin.ai/x?tags=a&tags=b&first=1"


async def test_http_errors_are_raised_with_context(
    client: DevinClient, request_mock: AsyncMock
) -> None:
    request_mock.return_value = _response(403, {"detail": "no"})

    with pytest.raises(httpx.HTTPStatusError, match="HTTP 403 for GET"):
        await client.send_api_request("GET", "/sessions")


async def test_empty_body_returns_empty_dict(
    client: DevinClient, request_mock: AsyncMock
) -> None:
    request_mock.return_value = _response(204)

    assert await client.send_api_request("DELETE", "/sessions/devin-1") == {}


async def test_paginate_follows_end_cursor(client: DevinClient) -> None:
    client.send_api_request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"items": [{"id": 1}], "end_cursor": "c1", "has_next_page": True},
            {"items": [{"id": 2}], "end_cursor": "c2", "has_next_page": False},
        ]
    )

    pages = [page async for page in client.paginate("/sessions", {"tags": ["x"]})]

    assert pages == [[{"id": 1}], [{"id": 2}]]
    second_params = client.send_api_request.await_args_list[1].kwargs["params"]
    assert second_params == {"tags": ["x"], "first": 100, "after": "c1"}


async def test_page_size_is_capped(client: DevinClient) -> None:
    send = AsyncMock(return_value={"items": []})
    client.send_api_request = send  # type: ignore[method-assign]

    await client.fetch_page("/sessions", page_size=500)

    assert _last_kwargs(send)["params"]["first"] == 200


async def test_paginate_yields_fetched_pages_then_raises(client: DevinClient) -> None:
    client.send_api_request = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"items": [{"id": 1}], "end_cursor": "c1", "has_next_page": True},
            http_error(500),
        ]
    )

    pages: list[list[dict[str, Any]]] = []
    with pytest.raises(DevinPaginationError):
        async for page in client.paginate("/sessions"):
            pages.append(page)

    assert pages == [[{"id": 1}]]


async def test_list_messages_after_walks_pages_and_returns_last_cursor(
    client: DevinClient,
) -> None:
    client.fetch_page = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {
                "items": [_message("e1")],
                "end_cursor": "c1",
                "has_next_page": True,
            },
            {"items": [_message("e2")], "end_cursor": "c2", "has_next_page": False},
        ]
    )

    messages, cursor = await DevinSessions(client).list_messages_after("devin-1", None)

    assert [m.event_id for m in messages] == ["e1", "e2"]
    assert cursor == "c2"
    assert client.fetch_page.await_args_list[1].kwargs["after"] == "c1"


async def test_list_messages_after_keeps_cursor_when_nothing_new(
    client: DevinClient,
) -> None:
    client.fetch_page = AsyncMock(  # type: ignore[method-assign]
        return_value={"items": [], "end_cursor": None, "has_next_page": False}
    )

    messages, cursor = await DevinSessions(client).list_messages_after("devin-1", "c9")

    assert messages == []
    assert cursor == "c9"


async def test_find_user_id_by_email(client: DevinClient) -> None:
    fetch_page = AsyncMock(
        return_value={"items": [{"user_id": "user-7", "email": "a@b.c"}]}
    )
    client.fetch_page = fetch_page  # type: ignore[method-assign]

    assert await DevinSessions(client).find_user_id_by_email("a@b.c") == "user-7"
    kwargs = _last_kwargs(fetch_page)
    assert kwargs["params"] == {"email": "a@b.c"}
    assert kwargs["absolute_path"] is True


async def test_find_user_id_by_email_not_found(client: DevinClient) -> None:
    client.fetch_page = AsyncMock(return_value={"items": []})  # type: ignore[method-assign]

    assert await DevinSessions(client).find_user_id_by_email("a@b.c") is None


def _message(event_id: str) -> dict[str, Any]:
    return {"event_id": event_id, "source": "devin", "message": "hi", "created_at": 1}
