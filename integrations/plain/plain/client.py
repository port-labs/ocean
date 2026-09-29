from collections.abc import AsyncGenerator
from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.context.resource import resource
from port_ocean.exceptions.context import ResourceContextNotFoundError
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.helpers.async_client import OceanAsyncClient

from plain.exceptions import (
    PlainGraphQLError,
    PlainHTTPError,
    missing_permission_names,
)
from plain.queries import (
    GET_CUSTOMER,
    GET_THREAD,
    LIST_COMPANIES,
    LIST_CUSTOMERS,
    LIST_TENANTS,
    LIST_THREAD_IDS,
    LIST_THREADS,
    LIST_USERS,
    THREAD_TIMELINE,
)
from plain.utils import edges_to_nodes, get_nested

DEFAULT_API_URL = "https://core-api.uk.plain.com/graphql/v1"
USER_AGENT = "port-ocean-plain"
DEFAULT_PAGE_SIZE = 100
MAX_PAGE_SIZE = 100


class PlainClient:
    """Authenticated client for Plain's GraphQL API."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        config = ocean.integration_config
        self._api_token = str(config["api_token"])
        api_url = config.get("api_url") or DEFAULT_API_URL
        self._api_url = str(api_url).rstrip("/")
        self._page_size = _resolve_page_size(config.get("page_size"))
        self._thread_statuses = _thread_statuses(config.get("thread_status_filter"))
        self._http_client = http_client or OceanAsyncClient(
            timeout=ocean.config.client_timeout,
            headers={"User-Agent": USER_AGENT},
        )

    async def execute(
        self,
        query: str,
        variables: dict[str, Any] | None = None,
        operation_name: str | None = None,
    ) -> dict[str, Any]:
        body: dict[str, Any] = {"query": query, "variables": variables or {}}
        if operation_name is not None:
            body["operationName"] = operation_name

        logger.debug(
            "Executing Plain GraphQL operation {}", operation_name or "anonymous"
        )
        response = await self._http_client.post(
            self._api_url,
            json=body,
            headers={
                "Authorization": f"Bearer {self._api_token}",
                "Content-Type": "application/json",
                "User-Agent": USER_AGENT,
            },
        )
        if response.status_code >= 400:
            _abort_when_permission_is_missing(response.text)
            raise PlainHTTPError(response.status_code, response.text)

        try:
            payload = response.json()
        except ValueError as error:
            raise PlainGraphQLError(
                [{"message": "Plain returned a non-JSON response"}]
            ) from error

        if not isinstance(payload, dict):
            raise PlainGraphQLError(
                [{"message": "Plain returned a response that is not an object"}]
            )

        errors = payload.get("errors")
        if errors:
            if not isinstance(errors, list):
                errors = [{"message": str(errors)}]
            _abort_when_permission_is_missing(errors)
            raise PlainGraphQLError(errors)

        data = payload.get("data")
        if not isinstance(data, dict):
            raise PlainGraphQLError(
                [{"message": "Plain returned a response without data"}]
            )
        return data

    async def paginate_connection(
        self,
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Yield each page of nodes from a Relay connection.

        ``connection_path`` is relative to the GraphQL ``data`` object returned
        by ``execute``. A leading ``data.`` is accepted so callers can pass
        paths such as ``data.companies``.
        """
        after: str | None = None
        lookup_path = _connection_lookup_path(connection_path)
        while True:
            page_variables = {
                **(variables or {}),
                "first": self._page_size,
                "after": after,
            }
            data = await self.execute(query, page_variables, operation_name)
            connection = get_nested(data, lookup_path)
            if not isinstance(connection, dict):
                raise PlainGraphQLError(
                    [
                        {
                            "message": (
                                f"Plain response is missing connection '{connection_path}'"
                            )
                        }
                    ]
                )

            page_info = connection.get("pageInfo")
            if not isinstance(page_info, dict):
                raise PlainGraphQLError(
                    [
                        {
                            "message": (
                                f"Plain connection '{connection_path}' is missing pageInfo"
                            )
                        }
                    ]
                )

            yield edges_to_nodes(connection)
            if not page_info.get("hasNextPage"):
                return

            end_cursor = page_info.get("endCursor")
            if not isinstance(end_cursor, str) or not end_cursor:
                raise PlainGraphQLError(
                    [{"message": ("Plain reported another page without an endCursor")}]
                )
            after = end_cursor

    async def get_companies(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_COMPANIES,
            "ListCompanies",
            None,
            "data.companies",
        ):
            yield batch

    async def get_tenants(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_TENANTS,
            "ListTenants",
            None,
            "data.tenants",
        ):
            yield batch

    async def get_users(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_USERS,
            "ListUsers",
            None,
            "data.users",
        ):
            yield batch

    async def get_customers(self) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_CUSTOMERS,
            "ListCustomers",
            None,
            "data.customers",
        ):
            yield batch

    async def get_threads(
        self, statuses: list[str] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_THREADS,
            "ListThreads",
            self._thread_list_variables(statuses),
            "data.threads",
        ):
            yield batch

    async def get_thread_ids(
        self, statuses: list[str] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_THREAD_IDS,
            "ListThreadIds",
            self._thread_list_variables(statuses),
            "data.threads",
        ):
            yield batch

    async def get_thread_messages(
        self, statuses: list[str] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for threads in self.get_thread_ids(statuses):
            for thread in threads:
                thread_id = thread.get("id")
                if not isinstance(thread_id, str) or not thread_id:
                    continue
                async for messages in self._timeline_pages(thread_id):
                    if messages:
                        yield messages

    def _thread_list_variables(
        self, statuses: list[str] | None
    ) -> dict[str, Any] | None:
        chosen = self._thread_statuses if statuses is None else statuses
        if not chosen:
            return None
        return {"filters": {"statuses": chosen}}

    async def _timeline_pages(
        self, thread_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        try:
            async for batch in self.paginate_connection(
                THREAD_TIMELINE,
                "ThreadTimeline",
                {"threadId": thread_id},
                "thread.timelineEntries",
            ):
                yield [entry for entry in batch if _has_message_text(entry)]
        except PlainGraphQLError as error:
            if "missing connection" in str(error):
                raise PlainGraphQLError(
                    [{"message": f"Plain thread '{thread_id}' was not found"}]
                ) from error
            raise

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_CUSTOMER,
            {"customerId": customer_id},
            "GetCustomer",
            "customer",
            customer_id,
            "customer",
        )

    async def get_thread(self, thread_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_THREAD,
            {"threadId": thread_id},
            "GetThread",
            "thread",
            thread_id,
            "thread",
        )

    async def _get_single_entity(
        self,
        query: str,
        variables: dict[str, Any],
        operation_name: str,
        field: str,
        entity_id: str,
        label: str,
    ) -> dict[str, Any]:
        data = await self.execute(query, variables, operation_name)
        entity = data.get(field)
        if not isinstance(entity, dict):
            raise PlainGraphQLError(
                [{"message": f"Plain {label} '{entity_id}' was not found"}]
            )
        return entity


def _abort_when_permission_is_missing(payload: Any) -> None:
    permissions = missing_permission_names(payload)
    if not permissions:
        return
    quoted = ", ".join(f'"{name}"' for name in permissions)
    noun = "permission" if len(permissions) == 1 else "permissions"
    try:
        kind = resource.kind
    except ResourceContextNotFoundError:
        message = f"The Plain API key is missing the {quoted} {noun}"
    else:
        message = (
            f"Failed to sync kind '{kind}': the Plain API key is missing "
            f"the {quoted} {noun}"
        )
    logger.error(message)
    raise OceanAbortException(message)


def _has_message_text(entry: dict[str, Any]) -> bool:
    text = entry.get("llmText")
    return isinstance(text, str) and bool(text.strip())


def _resolve_page_size(raw: Any) -> int:
    try:
        size = int(raw)
    except (TypeError, ValueError):
        return DEFAULT_PAGE_SIZE
    if size < 1:
        return DEFAULT_PAGE_SIZE
    return min(size, MAX_PAGE_SIZE)


def _thread_statuses(raw: Any) -> list[str]:
    if isinstance(raw, str):
        values = raw.split(",")
    elif isinstance(raw, list):
        values = [str(value) for value in raw]
    else:
        return []
    return [value.strip() for value in values if value.strip()]


def _connection_lookup_path(connection_path: str) -> str:
    if connection_path.startswith("data."):
        return connection_path.removeprefix("data.")
    return connection_path
