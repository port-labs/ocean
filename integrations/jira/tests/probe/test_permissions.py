from jira.overrides import JiraPortAppConfig
from jira.probe.permissions import (
    JiraKindPermissionVerdict,
    authentication_failure_message,
    message_with_required_scopes,
)
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)


def test_jira_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    # Arrange
    verdict = JiraKindPermissionVerdict()

    # Act + Assert
    assert verdict.kind_permissions == get_kind_probe_permissions(JiraPortAppConfig)
    assert "team" not in verdict.kind_permissions


def test_message_with_required_scopes_appends_scope_list() -> None:
    # Act + Assert
    assert message_with_required_scopes(
        "Failed to verify Jira authentication.",
        ("read:jira-user",),
    ) == ("Failed to verify Jira authentication. Required scope(s): read:jira-user.")
    assert (
        message_with_required_scopes("Connection failed.", ()) == "Connection failed."
    )


def test_authentication_failure_message_for_401_mentions_url_email_and_scopes() -> None:
    # Act + Assert
    assert authentication_failure_message(status_code=401) == (
        "Failed to verify Jira authentication. "
        "Ensure the Jira URL, email, and an API token with the "
        "read:jira-user scope are all valid."
    )


def test_authentication_failure_message_for_404_points_at_url() -> None:
    # Act + Assert
    assert authentication_failure_message(status_code=404) == (
        "Could not find the Jira site at the configured URL, "
        "please ensure the Jira URL is correct."
    )


def test_authentication_failure_message_for_other_status_avoids_http_jargon() -> None:
    # Act + Assert
    assert authentication_failure_message(status_code=500) == (
        "Could not verify the connection to Jira. "
        "Ensure the Jira URL is correct and that Jira is reachable."
    )
