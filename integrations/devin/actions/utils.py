from typing import Any

import httpx
from port_ocean.context.ocean import ocean

from actions.exceptions import DevinApiError, InvalidActionParametersException
from clients.models import SessionResponse
from core.sessions import DevinSessions
from core.tracking.tags import MANAGED_TAG, reserved_tags

ALLOWED_CONFIG_KEYS = frozenset({"devin_mode", "attachment_urls"})


def installation_id() -> str:
    return ocean.config.integration.identifier


def merge_config(
    config: dict[str, Any] | None, typed: dict[str, Any]
) -> dict[str, Any]:
    """Shallow-merge typed inputs onto an allowlisted `config` slice of the API body."""
    body: dict[str, Any] = {}
    if config:
        unknown = set(config) - ALLOWED_CONFIG_KEYS
        if unknown:
            raise InvalidActionParametersException(
                "config may only set "
                f"{sorted(ALLOWED_CONFIG_KEYS)}; unsupported keys: {sorted(unknown)}"
            )
        body.update({key: value for key, value in config.items() if value is not None})
    body.update({key: value for key, value in typed.items() if value is not None})
    return body


def ensure_no_reserved_tags(tags: list[str]) -> None:
    if reserved := reserved_tags(tags):
        raise InvalidActionParametersException(
            f"Tags starting with 'port:' are reserved for the integration: {reserved}"
        )


def ensure_port_managed_session(session: SessionResponse) -> None:
    if MANAGED_TAG not in session.tags:
        raise InvalidActionParametersException(
            f"Session {session.session_id} was not created through Port "
            f"({MANAGED_TAG} tag missing)"
        )


def ensure_session_accepts_message(
    status: str, status_detail: str | None, session_id: str
) -> None:
    if status == "exit":
        raise InvalidActionParametersException(
            f"Session {session_id} has already ended"
        )
    if status == "error":
        raise InvalidActionParametersException(
            f"Session {session_id} is in an error state"
        )
    if status == "suspended" and status_detail == "user_request":
        raise InvalidActionParametersException(
            f"Session {session_id} was stopped and cannot accept messages"
        )


async def resolve_user_id(
    sessions: DevinSessions, email: str | None, run: object
) -> str | None:
    """Resolve a Devin org member by email. Unset email means the service user."""
    del run
    if not email:
        return None
    try:
        user_id = await sessions.find_user_id_by_email(email)
    except httpx.HTTPError as error:
        raise DevinApiError.from_http_error(
            error, f"Failed to look up Devin organization member {email}"
        ) from error
    if user_id is None:
        raise InvalidActionParametersException(
            f"No Devin organization member found for email {email}"
        )
    return user_id
