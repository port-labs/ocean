from unittest.mock import AsyncMock

import pytest

from plain.exceptions import PlainGraphQLError
from plain.queries import GET_CUSTOMER, GET_THREAD
from tests.kind_helpers import make_client


async def test_get_thread_returns_node() -> None:
    client = make_client()
    thread = {
        "id": "th_1",
        "title": "Login help",
        "assignedTo": {"__typename": "User", "id": "us_1"},
    }
    client.execute = AsyncMock(return_value={"thread": thread})  # type: ignore[method-assign]

    result = await client.get_thread("th_1")

    assert result == thread
    assert result["assignedTo"]["__typename"] == "User"
    client.execute.assert_awaited_once_with(
        GET_THREAD,
        {"threadId": "th_1"},
        "GetThread",
    )


async def test_get_customer_returns_node() -> None:
    client = make_client()
    customer = {"id": "c_1", "fullName": "Ada Lovelace", "company": {"id": "co_1"}}
    client.execute = AsyncMock(return_value={"customer": customer})  # type: ignore[method-assign]

    result = await client.get_customer("c_1")

    assert result == customer
    client.execute.assert_awaited_once_with(
        GET_CUSTOMER,
        {"customerId": "c_1"},
        "GetCustomer",
    )


async def test_get_thread_raises_on_graphql_error() -> None:
    client = make_client()
    client.execute = AsyncMock(  # type: ignore[method-assign]
        side_effect=PlainGraphQLError([{"message": "Missing permission thread:read"}])
    )

    with pytest.raises(PlainGraphQLError, match="Missing permission thread:read"):
        await client.get_thread("th_1")


async def test_get_thread_raises_when_entity_is_missing() -> None:
    client = make_client()
    client.execute = AsyncMock(return_value={"thread": None})  # type: ignore[method-assign]

    with pytest.raises(
        PlainGraphQLError, match="Plain thread 'th_missing' was not found"
    ):
        await client.get_thread("th_missing")


async def test_get_customer_raises_when_entity_is_missing() -> None:
    client = make_client()
    client.execute = AsyncMock(return_value={"customer": None})  # type: ignore[method-assign]

    with pytest.raises(
        PlainGraphQLError, match="Plain customer 'c_missing' was not found"
    ):
        await client.get_customer("c_missing")
