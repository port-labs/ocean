from unittest.mock import AsyncMock

import pytest

from plain.exceptions import PlainGraphQLError
from plain.queries import (
    GET_COMPANY,
    GET_CUSTOMER,
    GET_DISCUSSION,
    GET_MACHINE_USER,
    GET_TENANT,
    GET_THREAD,
    GET_TIMELINE_ENTRY,
    GET_USER,
)
from tests.kind_helpers import make_client


async def test_get_company_tenant_user_discussion_and_timeline() -> None:
    client = make_client()
    client.execute = AsyncMock(  # type: ignore[method-assign]
        side_effect=[
            {"company": {"id": "co_1", "name": "Acme"}},
            {"tenant": {"id": "te_1", "name": "Tenant"}},
            {"user": {"id": "us_1", "email": "a@b.com"}},
            {"machineUser": {"id": "mu_1", "fullName": "Bot"}},
            {"discussion": {"id": "disc_1", "threadId": "th_1"}},
            {
                "timelineEntry": {
                    "id": "tl_1",
                    "threadId": "th_1",
                    "llmText": "Hello",
                }
            },
        ]
    )

    assert (await client.get_company("co_1"))["id"] == "co_1"
    assert (await client.get_tenant("te_1"))["id"] == "te_1"
    assert (await client.get_user("us_1"))["id"] == "us_1"
    assert (await client.get_machine_user("mu_1"))["id"] == "mu_1"
    assert (await client.get_discussion("disc_1"))["id"] == "disc_1"
    assert (await client.get_timeline_entry("c_1", "tl_1"))["id"] == "tl_1"

    assert client.execute.await_args_list[0].args[0] is GET_COMPANY
    assert client.execute.await_args_list[1].args[0] is GET_TENANT
    assert client.execute.await_args_list[2].args[0] is GET_USER
    assert client.execute.await_args_list[3].args[0] is GET_MACHINE_USER
    assert client.execute.await_args_list[4].args[0] is GET_DISCUSSION
    assert client.execute.await_args_list[5].args[0] is GET_TIMELINE_ENTRY


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
