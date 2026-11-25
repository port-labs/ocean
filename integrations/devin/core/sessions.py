from collections.abc import AsyncGenerator
from typing import Any

from clients import endpoints
from clients.devin_client import DevinClient
from clients.models import SessionMessage, SessionResponse
from clients.parsing import (
    parse_session_message_best_effort,
    parse_session_response_best_effort,
    require_session_response,
)


class DevinSessions:
    def __init__(self, client: DevinClient) -> None:
        self.client = client

    async def create(self, body: dict[str, Any]) -> SessionResponse:
        data = await self.client.send_api_request(
            "POST", endpoints.SESSIONS, json_body=body
        )
        return require_session_response(data)

    async def get(self, session_id: str) -> SessionResponse:
        data = await self.client.send_api_request("GET", endpoints.session(session_id))
        return require_session_response(data)

    async def list_by_tag(
        self, tag: str
    ) -> AsyncGenerator[list[SessionResponse], None]:
        async for page in self.client.paginate(
            endpoints.SESSIONS, params={"tags": [tag]}
        ):
            page_sessions: list[SessionResponse] = []
            for item in page:
                if session := parse_session_response_best_effort(item):
                    page_sessions.append(session)
            if page_sessions:
                yield page_sessions

    async def send_message(
        self, session_id: str, body: dict[str, Any]
    ) -> SessionResponse:
        data = await self.client.send_api_request(
            "POST", endpoints.session_messages(session_id), json_body=body
        )
        return require_session_response(data)

    async def list_messages_after(
        self, session_id: str, after: str | None
    ) -> tuple[list[SessionMessage], str | None]:
        # When no page is returned, keep `after` so the cursor does not move backward.
        messages: list[SessionMessage] = []
        cursor = after
        params = {"after": after} if after else None
        async for payload in self.client.paginate(
            endpoints.session_messages(session_id),
            params=params,
            envelopes=True,
        ):
            for item in payload.get("items") or []:
                if message := parse_session_message_best_effort(item):
                    messages.append(message)
            cursor = payload.get("end_cursor") or cursor
        return messages, cursor

    async def append_tags(self, session_id: str, tags: list[str]) -> list[str]:
        data = await self.client.send_api_request(
            "POST", endpoints.session_tags(session_id), json_body={"tags": tags}
        )
        return list(data.get("tags") or [])

    async def replace_tags(self, session_id: str, tags: list[str]) -> list[str]:
        data = await self.client.send_api_request(
            "PUT", endpoints.session_tags(session_id), json_body={"tags": tags}
        )
        return list(data.get("tags") or [])

    async def terminate(self, session_id: str, archive: bool) -> SessionResponse:
        data = await self.client.send_api_request(
            "DELETE", endpoints.session(session_id), params={"archive": archive}
        )
        return require_session_response(data)

    async def archive(self, session_id: str) -> SessionResponse:
        data = await self.client.send_api_request(
            "POST", endpoints.session_archive(session_id)
        )
        return require_session_response(data)
