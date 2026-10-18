from jira.overrides import JiraPortAppConfig
from jira.probe.permissions import (
    JiraKindPermissionVerdict,
    message_with_required_scopes,
)
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)


def test_jira_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    verdict = JiraKindPermissionVerdict()

    assert verdict.kind_permissions == get_kind_probe_permissions(JiraPortAppConfig)
    assert "team" not in verdict.kind_permissions


def test_message_with_required_scopes_appends_scope_list() -> None:
    assert message_with_required_scopes(
        "Failed to verify Jira authentication.",
        ("read:jira-user",),
    ) == (
        "Failed to verify Jira authentication. Required scope(s): read:jira-user."
    )
    assert (
        message_with_required_scopes("Connection failed.", ()) == "Connection failed."
    )
