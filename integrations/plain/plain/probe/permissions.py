from integration import PlainPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination

# Permissions required by the probe's myPermissions auth call itself.
MY_PERMISSIONS_REQUIRED: tuple[str, ...] = ()


def authentication_failure_message(*, status_code: int | None = None) -> str:
    if status_code == 401:
        return (
            "Failed to verify Plain authentication. "
            "Ensure the API URL and API token are valid."
        )
    if status_code == 404:
        return (
            "Could not find the Plain GraphQL endpoint at the configured URL, "
            "please ensure the API URL is correct."
        )
    if status_code is not None:
        return (
            "Could not verify the connection to Plain. "
            "Ensure the API URL is correct and that Plain is reachable."
        )
    return (
        "Failed to verify Plain authentication. "
        "Ensure the API URL and API token are valid."
    )


class PlainKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return get_kind_probe_permissions(PlainPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def granted_message(self, granted: tuple[str, ...]) -> str:
        if len(granted) == 1:
            return f"Plain access verified ({granted[0]})"
        return "Plain access verified: " + ", ".join(granted)
