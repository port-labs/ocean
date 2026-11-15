from typing import Any

from actions.exceptions import InvalidActionParametersException
from clients.models import SessionResponse
from core.tracking.tags import MANAGED_TAG, reserved_tags

ALLOWED_CONFIG_KEYS = frozenset({"devin_mode", "attachment_urls"})


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


def validate_session_active(
    status: str, status_detail: str | None, session_id: str
) -> None:
    """Reject ``send_message`` when the session is ended, failed, or user-stopped."""
    match (status, status_detail):
        case ("exit", _):
            raise InvalidActionParametersException(
                f"Session {session_id} has already ended"
            )
        case ("error", _):
            raise InvalidActionParametersException(
                f"Session {session_id} is in an error state"
            )
        case ("suspended", "user_request"):
            raise InvalidActionParametersException(
                f"Session {session_id} was stopped and cannot accept messages"
            )
        case _:
            return
