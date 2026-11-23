from http import HTTPStatus

from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination

from datadog.overrides import DataDogPortAppConfig

ACCESS_DENIED_STATUS_CODES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})

# Scope-only permissions: Datadog doesn't assign them to roles, so they're absent
# from a user's role permissions, yet every user holds them. A scoped application
# key holds them only when they're among its scopes.
IMPLICIT_PERMISSIONS = frozenset({"teams_read", "user_access_read"})

# Needed by the probe itself to read the application key owner's permissions.
PERMISSIONS_LOOKUP_REQUIRED_SCOPE = "user_access_read"


def authentication_failure_message(
    *, status_code: int, invalid_key: str | None = None
) -> str:
    # Datadog rejects keys from another site with the same 401/403 as invalid
    # keys, so (like Jira's 401 hint) a rejected API key or token also points at
    # the base URL. A valid API key with a rejected application key means the
    # site is right, so that message names the application key alone.
    if status_code in ACCESS_DENIED_STATUS_CODES:
        if invalid_key == "application key":
            return (
                "Failed to verify Datadog authentication. "
                "Ensure the application key is valid."
            )
        credential = invalid_key or "Datadog credentials"
        verb = "are" if invalid_key is None else "is"
        return (
            "Failed to verify Datadog authentication. "
            f"Ensure the {credential} {verb} valid and the Datadog base URL "
            "matches your Datadog site."
        )
    if status_code == HTTPStatus.NOT_FOUND:
        return (
            "Could not find the Datadog API at the configured base URL, "
            "please ensure the Datadog base URL matches your Datadog site."
        )
    return (
        "Could not verify the connection to Datadog. "
        "Ensure the Datadog base URL is correct and that Datadog is reachable."
    )


def permissions_lookup_failure_message(status_code: int) -> str:
    return (
        f"Datadog returned HTTP {status_code} while fetching user permissions. "
        f"Required scope(s): {PERMISSIONS_LOOKUP_REQUIRED_SCOPE}."
    )


def unverified_scopes_message(orgs: list[str] | None = None) -> str:
    """Probe-level note when the credentials' own scopes couldn't be read, so the
    verdicts reflect the owner's role only (*orgs*: the affected orgs, multi-org)."""
    message = (
        "Credentials are valid, but the scopes of the application key or access "
        "token could not be verified, so permissions were checked against the "
        "owner's role only. A kind can still fail to sync if the credentials are "
        "scoped without its permissions."
    )
    if orgs:
        message += f" Affected org(s): {', '.join(orgs)}."
    return message


class DatadogKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return get_kind_probe_permissions(DataDogPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def granted_message(self, granted: tuple[str, ...]) -> str:
        return f"Datadog access verified: {', '.join(granted)}"
