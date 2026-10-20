from typing import Any

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.models import IntegrationRun

from actions.exceptions import InvalidActionParametersException
from core.sessions import DevinSessions
from core.tracking.tags import reserved_tags


def installation_id() -> str:
    return ocean.config.integration.identifier


def merge_config(
    config: dict[str, Any] | None, typed: dict[str, Any]
) -> dict[str, Any]:
    """Shallow-merge typed inputs onto `config`; unset typed inputs don't override it."""
    body = dict(config or {})
    body.update({key: value for key, value in typed.items() if value is not None})
    return body


def ensure_no_reserved_tags(tags: list[str]) -> None:
    if reserved := reserved_tags(tags):
        raise InvalidActionParametersException(
            f"Tags starting with 'port:' are reserved for the integration: {reserved}"
        )


async def resolve_user_id(
    sessions: DevinSessions, email: str | None, run: IntegrationRun
) -> str | None:
    """Resolve a Devin org member by email; fall back to the service user."""
    if not email:
        return None
    try:
        user_id = await sessions.find_user_id_by_email(email)
    except httpx.HTTPError as error:
        logger.warning(f"Devin user lookup for {email} failed: {error}")
        user_id = None
    if user_id is None:
        await ocean.port_client.post_run_log(
            run,
            f"No Devin organization member found for {email}; "
            "continuing as the integration's service user",
            level="WARNING",
            should_raise=False,
        )
    return user_id
