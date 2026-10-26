from integration import PlainPortAppConfig
from plain.probe.permissions import (
    PlainKindPermissionVerdict,
    authentication_failure_message,
)
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
)
from port_ocean.core.probe import ProbeCheckStatus


def test_plain_kind_permission_verdict_loads_kind_probe_permissions() -> None:
    verdict = PlainKindPermissionVerdict()

    assert verdict.kind_permissions == get_kind_probe_permissions(PlainPortAppConfig)
    assert verdict.kind_permissions["company"] == ("company:read",)
    assert verdict.kind_permissions["user"] == ("user:read", "roles:read")
    assert verdict.kind_permissions["thread-message"] == (
        "thread:read",
        "timeline:read",
    )
    assert verdict.kind_permissions["discussion"] == (
        "thread:read",
        "threadDiscussion:read",
    )
    assert verdict.kind_permissions["discussion-message"] == (
        "thread:read",
        "threadDiscussion:read",
        "threadDiscussionMessage:read",
    )


def test_plain_kind_permission_verdict_success_and_failure() -> None:
    verdict = PlainKindPermissionVerdict()

    status, message = verdict.verdict(
        "company",
        {"company:read": True},
    )
    assert status is ProbeCheckStatus.SUCCESS
    assert "company:read" in message

    status, message = verdict.verdict(
        "user",
        {"user:read": True},
    )
    assert status is ProbeCheckStatus.FAILURE
    assert message == "Missing permission(s): roles:read"


def test_authentication_failure_message_for_401() -> None:
    assert authentication_failure_message(status_code=401) == (
        "Failed to verify Plain authentication. "
        "Ensure the API URL and API token are valid."
    )


def test_authentication_failure_message_for_404() -> None:
    assert authentication_failure_message(status_code=404) == (
        "Could not find the Plain GraphQL endpoint at the configured URL, "
        "please ensure the API URL is correct."
    )


def test_authentication_failure_message_for_other_status() -> None:
    assert authentication_failure_message(status_code=500) == (
        "Could not verify the connection to Plain. "
        "Ensure the API URL is correct and that Plain is reachable."
    )
