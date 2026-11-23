from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from actions.exceptions import InvalidActionParametersException
from clients.models import SessionResponse
from core.tracking.tags import MANAGED_TAG, reserved_tags

ALLOWED_CONFIG_KEYS = frozenset({"devin_mode", "attachment_urls"})


def merge_config(
    config: dict[str, Any] | None, typed: dict[str, Any]
) -> dict[str, Any]:
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


def _session_continuity_error(
    status: str, status_detail: str | None, session_id: str
) -> str | None:
    if status == "exit":
        return f"Session {session_id} has already ended"
    if status == "error":
        return f"Session {session_id} is in an error state"
    if status == "suspended" and status_detail == "user_request":
        return f"Session {session_id} was stopped and cannot accept messages"
    return None


def ensure_session_continuable(session: SessionResponse) -> None:
    if message := _session_continuity_error(
        session.status, session.status_detail, session.session_id
    ):
        raise InvalidActionParametersException(message)


async def upsert_raw(kind: str, raw: dict[str, Any]) -> None:
    await ocean.register_raw(kind, [raw])


async def upsert_raw_best_effort(
    kind: str, raw: dict[str, Any], run: IntegrationRun | None = None
) -> None:
    try:
        await upsert_raw(kind, raw)
    except Exception as error:
        message = f"Failed to upsert {kind} into the catalog (continuing): {error}"
        logger.warning(message)
        if run is None:
            return
        try:
            await ocean.port_client.post_run_log(run, message, level="WARNING")
        except Exception as log_error:
            logger.warning(
                f"Failed to post run log for catalog upsert failure: {log_error}"
            )
