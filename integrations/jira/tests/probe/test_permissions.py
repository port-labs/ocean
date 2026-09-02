from jira.overrides import JiraPortAppConfig
from jira.probe import JiraKindPermissionVerdict
from jira.probe.permissions import JiraKindPermissionVerdict as PermissionsVerdict
from port_ocean.core.handlers.port_app_config.validators import get_kind_probe_permissions
from port_ocean.core.probe import ProbeCheckStatus


def test_jira_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    verdict = JiraKindPermissionVerdict()

    assert verdict.kind_permissions == get_kind_probe_permissions(JiraPortAppConfig)
    assert verdict.kind_permissions["user"] == ("USER_PICKER",)
    assert "team" not in verdict.kind_permissions


def test_jira_kind_permission_verdict_grants_and_denies_permissions() -> None:
    verdict = PermissionsVerdict()

    granted_status, granted_message = verdict.verdict(
        "project",
        {"BROWSE_PROJECTS": True},
    )
    denied_status, denied_message = verdict.verdict(
        "user",
        {"USER_PICKER": False},
    )

    assert granted_status is ProbeCheckStatus.SUCCESS
    assert granted_message == "Permission(s) granted: BROWSE_PROJECTS"
    assert denied_status is ProbeCheckStatus.FAILURE
    assert denied_message == "Missing permission(s): USER_PICKER"
