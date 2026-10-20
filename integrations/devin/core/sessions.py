from collections.abc import AsyncGenerator
from typing import Any

from clients import endpoints
from clients.devin_client import DevinClient
from clients.models import SessionMessage, SessionResponse


class DevinSessions:
    """Session operations shared by the action executors and the session tracker.

    Kept apart from `DevinClient` so the client stays a generic transport and
    the resource-specific paths and payload shapes live in one place.
    """

    def __init__(self, client: DevinClient) -> None:
        self.client = client

    async def create(self, body: dict[str, Any]) -> SessionResponse:
        data = await self.client.send_api_request(
            "POST", endpoints.SESSIONS, json_body=body
        )
        return SessionResponse.model_validate(data)

    async def get(self, session_id: str) -> SessionResponse:
        data = await self.client.send_api_request("GET", endpoints.session(session_id))
        return SessionResponse.model_validate(data)

    async def list_by_tag(
        self, tag: str
    ) -> AsyncGenerator[list[SessionResponse], None]:
        async for page in self.client.paginate(
            endpoints.SESSIONS, params={"tags": [tag]}
        ):
            yield [SessionResponse.model_validate(item) for item in page]

    async def send_message(
        self, session_id: str, body: dict[str, Any]
    ) -> SessionResponse:
        data = await self.client.send_api_request(
            "POST", endpoints.session_messages(session_id), json_body=body
        )
        return SessionResponse.model_validate(data)

    async def list_messages_after(
        self, session_id: str, after: str | None
    ) -> tuple[list[SessionMessage], str | None]:
        """Return every message after `after` (all messages when it is `None`)
        and the cursor to resume from next time.

        The returned cursor is `after` itself when no new page was produced, so
        a caller can always store it without losing its place.
        """
        messages: list[SessionMessage] = []
        cursor = after
        while True:
            payload = await self.client.fetch_page(
                endpoints.session_messages(session_id), after=cursor
            )
            messages.extend(
                SessionMessage.model_validate(item)
                for item in payload.get("items") or []
            )
            cursor = payload.get("end_cursor") or cursor
            if not payload.get("has_next_page") or not payload.get("end_cursor"):
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
        return SessionResponse.model_validate(data)

    async def archive(self, session_id: str) -> SessionResponse:
        data = await self.client.send_api_request(
            "POST", endpoints.session_archive(session_id)
        )
        return SessionResponse.model_validate(data)

    async def find_user_id_by_email(self, email: str) -> str | None:
        data = await self.client.fetch_page(
            endpoints.members_users_beta(self.client.org_id),
            params={"email": email},
            page_size=1,
            absolute_path=True,
        )
        for user in data.get("items") or []:
            if isinstance(user, dict) and user.get("user_id"):
                return str(user["user_id"])
        return None
