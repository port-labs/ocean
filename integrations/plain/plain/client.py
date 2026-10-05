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
from plain.constants import (
    WEBHOOK_EVENT_TYPES,
    WEBHOOK_NAME,
    WEBHOOK_PATH_SUFFIX,
    WEBHOOK_TARGET_VERSION,
)
from plain.queries import (
    CREATE_WEBHOOK_TARGET,
    DISCUSSION_MESSAGES,
    GET_COMPANY,
    GET_CUSTOMER,
    GET_DISCUSSION,
    GET_TENANT,
    GET_THREAD,
    GET_TIMELINE_ENTRY,
    GET_MACHINE_USER,
    GET_USER,
    LIST_COMPANIES,
    LIST_CUSTOMERS,
    LIST_MACHINE_USERS,
    LIST_TENANTS,
    LIST_THREAD_IDS,
    LIST_THREADS,
    LIST_USERS,
    LIST_WEBHOOK_TARGETS,
    THREAD_DISCUSSION_IDS,
    THREAD_DISCUSSIONS,
    THREAD_TIMELINE,
    UPDATE_WEBHOOK_TARGET,
)
from plain.utils import edges_to_nodes, get_nested, is_ai_discussion

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
            # GraphQL is POST-only; Ocean RetryTransport skips POST unless opted in.
            extensions={"retryable": True},
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

    async def get_machine_users(
        self, *, exclude_deleted: bool = False
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            LIST_MACHINE_USERS,
            "ListMachineUsers",
            None,
            "data.machineUsers",
        ):
            if exclude_deleted:
                batch = [user for user in batch if not user.get("isDeleted")]
                if not batch:
                    continue
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

    async def get_discussions(
        self,
        statuses: list[str] | None = None,
        *,
        exclude_ai_discussions: bool = False,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for threads in self.get_thread_ids(statuses):
            for thread in threads:
                thread_id = _entity_id(thread)
                if thread_id is None:
                    continue
                async for discussions in self._discussion_pages(thread_id):
                    if exclude_ai_discussions:
                        discussions = [
                            discussion
                            for discussion in discussions
                            if not is_ai_discussion(discussion)
                        ]
                    if discussions:
                        yield discussions

    async def get_discussion_messages(
        self,
        statuses: list[str] | None = None,
        *,
        exclude_ai_discussions: bool = False,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for threads in self.get_thread_ids(statuses):
            for thread in threads:
                thread_id = _entity_id(thread)
                if thread_id is None:
                    continue
                async for discussions in self._discussion_id_pages(thread_id):
                    for discussion in discussions:
                        if exclude_ai_discussions and is_ai_discussion(discussion):
                            continue
                        discussion_id = _entity_id(discussion)
                        if discussion_id is None:
                            continue
                        async for messages in self._discussion_message_pages(
                            discussion_id
                        ):
                            stamped = [
                                {**message, "threadId": thread_id}
                                for message in messages
                            ]
                            if stamped:
                                yield stamped

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

    async def _discussion_pages(
        self, thread_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            THREAD_DISCUSSIONS,
            "ThreadDiscussions",
            {"threadId": thread_id},
            "discussions",
        ):
            yield batch

    async def _discussion_id_pages(
        self, thread_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for batch in self.paginate_connection(
            THREAD_DISCUSSION_IDS,
            "ThreadDiscussionIds",
            {"threadId": thread_id},
            "discussions",
        ):
            yield batch

    async def _discussion_message_pages(
        self, discussion_id: str
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        try:
            async for batch in self.paginate_connection(
                DISCUSSION_MESSAGES,
                "DiscussionMessages",
                {"discussionId": discussion_id},
                "discussion.messages",
            ):
                yield batch
        except PlainGraphQLError as error:
            if "missing connection" in str(error):
                raise PlainGraphQLError(
                    [{"message": f"Plain discussion '{discussion_id}' was not found"}]
                ) from error
            raise

    async def get_company(self, company_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_COMPANY,
            {"companyId": company_id},
            "GetCompany",
            "company",
            company_id,
            "company",
        )

    async def get_tenant(self, tenant_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_TENANT,
            {"tenantId": tenant_id},
            "GetTenant",
            "tenant",
            tenant_id,
            "tenant",
        )

    async def get_user(self, user_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_USER,
            {"userId": user_id},
            "GetUser",
            "user",
            user_id,
            "user",
        )

    async def get_machine_user(self, machine_user_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_MACHINE_USER,
            {"machineUserId": machine_user_id},
            "GetMachineUser",
            "machineUser",
            machine_user_id,
            "machine user",
        )

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

    async def get_discussion(self, discussion_id: str) -> dict[str, Any]:
        return await self._get_single_entity(
            GET_DISCUSSION,
            {"discussionId": discussion_id},
            "GetDiscussion",
            "discussion",
            discussion_id,
            "discussion",
        )

    async def get_timeline_entry(
        self, customer_id: str, timeline_entry_id: str
    ) -> dict[str, Any]:
        data = await self.execute(
            GET_TIMELINE_ENTRY,
            {
                "customerId": customer_id,
                "timelineEntryId": timeline_entry_id,
            },
            "GetTimelineEntry",
        )
        entry = data.get("timelineEntry")
        if not isinstance(entry, dict):
            raise PlainGraphQLError(
                [
                    {
                        "message": (
                            f"Plain timeline entry '{timeline_entry_id}' was not found"
                        )
                    }
                ]
            )
        if not _has_message_text(entry):
            raise PlainGraphQLError(
                [
                    {
                        "message": (
                            f"Plain timeline entry '{timeline_entry_id}' has no message text"
                        )
                    }
                ]
            )
        return entry

    async def get_discussion_message(
        self, discussion_id: str, message_id: str, thread_id: str | None = None
    ) -> dict[str, Any]:
        resolved_thread_id = thread_id
        if resolved_thread_id is None:
            discussion = await self.get_discussion(discussion_id)
            raw_thread_id = discussion.get("threadId")
            if isinstance(raw_thread_id, str) and raw_thread_id:
                resolved_thread_id = raw_thread_id

        async for messages in self._discussion_message_pages(discussion_id):
            for message in messages:
                if message.get("id") == message_id:
                    stamped = dict(message)
                    if resolved_thread_id:
                        stamped["threadId"] = resolved_thread_id
                    return stamped

        raise PlainGraphQLError(
            [
                {
                    "message": (
                        f"Plain discussion message '{message_id}' was not found "
                        f"in discussion '{discussion_id}'"
                    )
                }
            ]
        )

    async def ensure_webhook_target(self, app_host: str) -> None:
        target_url = f"{app_host.rstrip('/')}{WEBHOOK_PATH_SUFFIX}"
        description = f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}"
        subscriptions = [{"eventType": event} for event in WEBHOOK_EVENT_TYPES]

        async for targets in self.paginate_connection(
            LIST_WEBHOOK_TARGETS,
            "ListWebhookTargets",
            None,
            "data.webhookTargets",
        ):
            for target in targets:
                if target.get("url") == target_url:
                    await self._update_webhook_target(
                        str(target["id"]),
                        subscriptions,
                    )
                    logger.info(
                        "Updated existing Plain webhook target for {}", target_url
                    )
                    return

        await self._create_webhook_target(target_url, description, subscriptions)
        logger.info("Created Plain webhook target for {}", target_url)

    async def _create_webhook_target(
        self,
        url: str,
        description: str,
        subscriptions: list[dict[str, str]],
    ) -> None:
        data = await self.execute(
            CREATE_WEBHOOK_TARGET,
            {
                "input": {
                    "url": url,
                    "description": description,
                    "isEnabled": True,
                    "version": WEBHOOK_TARGET_VERSION,
                    "eventSubscriptions": subscriptions,
                }
            },
            "CreateWebhookTarget",
        )
        _raise_on_mutation_error(data.get("createWebhookTarget"), "createWebhookTarget")

    async def _update_webhook_target(
        self,
        webhook_target_id: str,
        subscriptions: list[dict[str, str]],
    ) -> None:
        data = await self.execute(
            UPDATE_WEBHOOK_TARGET,
            {
                "input": {
                    "webhookTargetId": webhook_target_id,
                    "isEnabled": {"value": True},
                    "version": {"value": WEBHOOK_TARGET_VERSION},
                    "eventSubscriptions": subscriptions,
                }
            },
            "UpdateWebhookTarget",
        )
        _raise_on_mutation_error(data.get("updateWebhookTarget"), "updateWebhookTarget")

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


def _raise_on_mutation_error(result: Any, mutation: str) -> None:
    if not isinstance(result, dict):
        raise PlainGraphQLError(
            [{"message": f"Plain {mutation} returned an unexpected response"}]
        )
    error = result.get("error")
    if isinstance(error, dict) and error.get("message"):
        raise PlainGraphQLError([error])


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


def _entity_id(entity: dict[str, Any]) -> str | None:
    entity_id = entity.get("id")
    if isinstance(entity_id, str) and entity_id:
        return entity_id
    return None


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
