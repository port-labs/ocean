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
    if status_code in ACCESS_DENIED_STATUS_CODES:
        if invalid_key:
            return f"Failed to verify Datadog authentication. Ensure the {invalid_key} is valid."
        return (
            "Failed to verify Datadog authentication. "
            "Ensure the Datadog credentials are valid."
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
    message = (
        f"Datadog returned HTTP {status_code} while reading the permissions "
        "of the application key's owner."
    )
    if status_code in ACCESS_DENIED_STATUS_CODES:
        message += (
            " If the application key is scoped, add the "
            f"{PERMISSIONS_LOOKUP_REQUIRED_SCOPE} scope to it."
        )
    return message


class DatadogKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return get_kind_probe_permissions(DataDogPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def denied_message(self, denied: tuple[str, ...]) -> str:
        return (
            super().denied_message(denied)
            + ". Grant them to the role of the application key's owner, "
            "and to the key's scopes if it is scoped."
        )
