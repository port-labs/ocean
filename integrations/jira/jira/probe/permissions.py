from jira.overrides import JiraPortAppConfig
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import KindPermissionVerdict, PermissionCombination

# Scopes required by the probe's auth / permission endpoints.
MYSELF_REQUIRED_SCOPES = ("read:jira-user",)
MYPERMISSIONS_REQUIRED_SCOPES = ("read:jira-work",)

def message_with_required_scopes(message: str, scopes: tuple[str, ...]) -> str:
    if not scopes:
        return message
    return f"{message} Required scope(s): {', '.join(scopes)}."


def _credentials_hint_with_scopes(scopes: tuple[str, ...]) -> str:
    if not scopes:
        return "Ensure the Jira URL, email, and API token are all valid."
    scope_list = ", ".join(scopes)
    scope_word = "scope" if len(scopes) == 1 else "scopes"
    return (
        f"Ensure the Jira URL, email, and an API token with the {scope_list} "
        f"{scope_word} are all valid."
    )


def authentication_failure_message(
    *,
    status_code: int | None = None,
    scopes: tuple[str, ...] = MYSELF_REQUIRED_SCOPES,
) -> str:
    # Jira returns the same 401 for a bad URL, email, token, or missing scoped-token
    # scopes, so 401 failures fold those inputs (and the needed scope) into one hint.
    if status_code == 401:
        return (
            "Failed to verify Jira authentication. "
            f"{_credentials_hint_with_scopes(scopes)}"
        )
    if status_code is not None:
        message = f"Failed to verify Jira authentication (HTTP {status_code})."
    else:
        message = "Failed to verify Jira authentication."
    return message_with_required_scopes(message, scopes)


class JiraKindPermissionVerdict(KindPermissionVerdict):
    def load_kind_permissions(self) -> dict[str, tuple[str, ...]]:
        return get_kind_probe_permissions(JiraPortAppConfig)

    @property
    def combination(self) -> PermissionCombination:
        return PermissionCombination.AND

    def granted_message(self, granted: tuple[str, ...]) -> str:
        if granted == ("BROWSE_PROJECTS",):
            return "Basic Jira access verified"
        return super().granted_message(granted)
