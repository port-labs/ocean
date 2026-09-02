from jira.overrides import JiraPortAppConfig
from jira.probe.permissions import JiraKindPermissionVerdict
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)


def test_jira_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    verdict = JiraKindPermissionVerdict()

    assert verdict.kind_permissions == get_kind_probe_permissions(JiraPortAppConfig)
    assert "team" not in verdict.kind_permissions
