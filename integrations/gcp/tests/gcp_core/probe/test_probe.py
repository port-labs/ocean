import asyncio
from types import SimpleNamespace
from collections.abc import AsyncIterator, Callable
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.api_core.exceptions import InvalidArgument, PermissionDenied, RetryError
from google.auth.exceptions import DefaultCredentialsError, GoogleAuthError

from port_ocean.core.handlers.port_app_config.models import CUSTOM_KIND
from port_ocean.core.probe import (
    ProbeCheck,
    ProbeCheckStatus,
    ProbeContext,
    ProbeStatus,
)

PROJECT = "cloudresourcemanager.googleapis.com/Project"
TOPIC = "pubsub.googleapis.com/Topic"
FOLDER = "cloudresourcemanager.googleapis.com/Folder"
ORGANIZATION = "cloudresourcemanager.googleapis.com/Organization"
CLOUD_FUNCTION = "gcpCloudFunction"
IAM_POLICY = "iamPolicy"


async def run_probe(context: ProbeContext) -> None:
    from gcp_core.probe.probe import GcpPermissionProbe

    await GcpPermissionProbe(context).run()
    # holds for every test: once run() returns, the probe has ended, so a check left
    # at PENDING would reach Port as a row the user can neither read nor act on
    unresolved = [
        c.kind for c in context.checks if c.status is ProbeCheckStatus.PENDING
    ]
    assert not unresolved, f"checks left pending: {unresolved}"


class FakePager:
    """Stands in for google-api-core's AsyncPager, which yields items across all pages.

    A page is only served once the consumer asks for an item on it, so `pages_served`
    shows how much was actually fetched.
    """

    def __init__(self, names: list[str], page_size: int = 3) -> None:
        self._names = names
        self._page_size = page_size
        self.pages_served = 0

    def __aiter__(self) -> AsyncIterator[SimpleNamespace]:
        async def generate() -> AsyncIterator[SimpleNamespace]:
            for start in range(0, len(self._names), self._page_size):
                self.pages_served += 1
                for name in self._names[start : start + self._page_size]:
                    yield SimpleNamespace(name=name)

        return generate()


def make_client(
    search_method: str,
    names: list[str],
    granted: list[str] | None = None,
    search_error: Exception | None = None,
) -> MagicMock:
    client = MagicMock()
    setattr(
        client,
        search_method,
        (
            AsyncMock(side_effect=search_error)
            if search_error
            else AsyncMock(return_value=FakePager(names))
        ),
    )
    client.test_iam_permissions = AsyncMock(
        side_effect=lambda request, **_: SimpleNamespace(
            permissions=[
                permission
                for permission in (granted or [])
                if permission in request["permissions"]
            ]
        )
    )
    return client


def checks_by_kind(context: ProbeContext) -> dict[str, ProbeCheck]:
    return {check.kind: check for check in context.checks}


@pytest.mark.asyncio
async def test_probe_succeeds_when_project_permissions_are_granted(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT, TOPIC]
    client = make_client(
        "search_projects",
        ["projects/sandbox"],
        granted=["resourcemanager.projects.get", "pubsub.topics.list"],
    )

    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.SUCCESS
    assert checks[TOPIC].status is ProbeCheckStatus.SUCCESS
    # One call per container, asking only for the permissions search doesn't imply.
    client.test_iam_permissions.assert_awaited_once()
    request: dict[str, Any] = client.test_iam_permissions.await_args.kwargs["request"]
    assert request["resource"] == "projects/sandbox"
    assert request["permissions"] == ["pubsub.topics.list"]


@pytest.mark.asyncio
async def test_probe_fails_only_the_kind_whose_permission_is_missing(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT, TOPIC]
    client = make_client(
        "search_projects",
        ["projects/sandbox"],
        granted=["resourcemanager.projects.get"],
    )

    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.SUCCESS
    assert checks[TOPIC].status is ProbeCheckStatus.FAILURE
    assert "1 of 1 project" in str(checks[TOPIC].message)
    assert "pubsub.topics.list" in str(checks[TOPIC].message)


@pytest.mark.asyncio
async def test_probe_reports_unknown_when_no_folder_is_discovered(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [FOLDER]
    client = make_client("search_folders", [])

    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[FOLDER]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert str(check.message) == (
        "No GCP folder was discovered. Search returns only folders where "
        "resourcemanager.folders.get is granted, so either none exist or the "
        "credentials are missing it."
    )
    client.test_iam_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_probe_fails_the_kind_when_discovery_is_denied(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [FOLDER]
    client = make_client(
        "search_folders",
        [],
        search_error=PermissionDenied("caller lacks folders.list"),
    )

    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[FOLDER]
    assert check.status is ProbeCheckStatus.FAILURE
    assert "Not allowed to list GCP folders" in str(check.message)


@pytest.mark.asyncio
async def test_probe_reports_unknown_for_a_kind_without_permission_mapping(
    probe_context: ProbeContext,
) -> None:
    from gcp_core.overrides import GCPCloudFunctionResourceConfig

    probe_context.available_kinds = [CLOUD_FUNCTION]

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[CLOUD_FUNCTION]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "No permission mapping is defined" in str(check.message)
    # the user-facing caveat is declared as probe_description, surfaced in the kinds schema
    assert GCPCloudFunctionResourceConfig.probe_description


@pytest.mark.asyncio
async def test_probe_fails_the_whole_probe_on_an_auth_error(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT, CLOUD_FUNCTION]
    client = make_client(
        "search_projects",
        [],
        search_error=DefaultCredentialsError("no ADC"),
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message is not None
    assert "Failed to verify GCP authentication" in probe_context.message
    # the probe has ended, so no check may still be sitting at PENDING - including
    # gcpCloudFunction, which belongs to no level and only the sweep ever resolves
    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.UNKNOWN
    assert "Could not verify project-level permissions" in str(checks[PROJECT].message)
    assert checks[CLOUD_FUNCTION].status is ProbeCheckStatus.UNKNOWN
    assert str(checks[CLOUD_FUNCTION].message) == (
        "No permission mapping is defined for gcpCloudFunction"
    )


@pytest.mark.asyncio
async def test_probe_reports_unknown_when_a_container_check_errors(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client("search_projects", ["projects/sandbox"])
    client.test_iam_permissions = AsyncMock(
        side_effect=PermissionDenied("cannot test permissions")
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "Could not verify access" in str(check.message)


@pytest.mark.asyncio
async def test_probe_counts_the_containers_sharing_a_verdict(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", [f"projects/p{index}" for index in range(10)]
    )
    granted_projects = {"projects/p0", "projects/p1", "projects/p2"}
    client.test_iam_permissions = AsyncMock(
        side_effect=lambda request, **_: SimpleNamespace(
            permissions=(
                ["pubsub.topics.list"]
                if request["resource"] in granted_projects
                else []
            )
        )
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    assert check.status is ProbeCheckStatus.FAILURE
    # too many to act on one by one, so the remedy is a grant higher up: count only
    assert (
        str(check.message)
        == "7 of 10 projects - Missing permission(s): pubsub.topics.list"
    )


@pytest.mark.asyncio
async def test_probe_caps_the_number_of_distinct_verdicts_listed(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", [f"projects/p{index}" for index in range(7)]
    )
    client.test_iam_permissions = AsyncMock(
        side_effect=[PermissionDenied(f"denied on p{index}") for index in range(7)]
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert str(check.message).count("Could not verify access") == 5
    assert "(and 2 more)" in str(check.message)


@pytest.mark.asyncio
async def test_probe_checks_the_organization_level(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [ORGANIZATION]
    client = make_client("search_organizations", ["organizations/123"])
    install_client("OrganizationsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[ORGANIZATION]
    assert check.status is ProbeCheckStatus.SUCCESS
    assert str(check.message) == (
        "Permission(s) granted: resourcemanager.organizations.get"
    )
    # search_organizations only returns organizations the caller can already get.
    client.test_iam_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_probe_checks_the_custom_kind_slot(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [CUSTOM_KIND]
    client = make_client(
        "search_projects",
        ["projects/sandbox"],
        granted=["cloudasset.assets.searchAllResources"],
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[CUSTOM_KIND]
    assert check.status is ProbeCheckStatus.SUCCESS


@pytest.mark.asyncio
async def test_probe_reports_an_unexpected_level_error_as_an_external_failure(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # neither a GCP API error nor an auth error, so it escapes the level
    probe_context.available_kinds = [PROJECT, FOLDER]
    projects = make_client("search_projects", [], search_error=TypeError("bad call"))
    folders = make_client("search_folders", [], search_error=RuntimeError("boom"))
    install_client("ProjectsAsyncClient", projects)
    install_client("FoldersAsyncClient", folders)

    await run_probe(probe_context)

    assert probe_context.status is ProbeStatus.FAILED
    message = str(probe_context.message)
    assert "Failed to verify GCP permissions" in message
    # both lanes are named, not just the first
    assert "TypeError" in message
    assert "RuntimeError" in message
    # each lane resolves its own checks on the way out
    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.UNKNOWN
    assert "Could not verify project-level permissions" in str(checks[PROJECT].message)
    assert checks[FOLDER].status is ProbeCheckStatus.UNKNOWN
    assert "Could not verify folder-level permissions" in str(checks[FOLDER].message)


@pytest.mark.asyncio
async def test_each_level_requests_only_its_own_kinds_permissions(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT, TOPIC, FOLDER, ORGANIZATION]
    clients = {
        "ProjectsAsyncClient": make_client("search_projects", ["projects/sandbox"]),
        "FoldersAsyncClient": make_client("search_folders", ["folders/1"]),
        "OrganizationsAsyncClient": make_client(
            "search_organizations", ["organizations/2"]
        ),
    }
    for name, client in clients.items():
        install_client(name, client)

    await run_probe(probe_context)

    # a permission that does not apply to the resource fails the WHOLE call with
    # 400 InvalidArgument, so a level may only send its own kinds' permissions
    projects_request = clients["ProjectsAsyncClient"].test_iam_permissions.await_args
    assert projects_request.kwargs["request"]["permissions"] == ["pubsub.topics.list"]
    # folder and organization have nothing left to test once discovery has run
    clients["FoldersAsyncClient"].test_iam_permissions.assert_not_awaited()
    clients["OrganizationsAsyncClient"].test_iam_permissions.assert_not_awaited()
    assert all(
        checks_by_kind(probe_context)[kind].status is ProbeCheckStatus.SUCCESS
        for kind in (PROJECT, FOLDER, ORGANIZATION)
    )


@pytest.mark.asyncio
async def test_probe_tests_containers_from_every_discovered_page(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    names = [f"projects/p{index}" for index in range(8)]
    pager = FakePager(names, page_size=3)
    client = make_client("search_projects", [], granted=["pubsub.topics.list"])
    client.search_projects = AsyncMock(return_value=pager)
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    assert pager.pages_served == 3
    assert client.search_projects.await_args.kwargs["request"] == {"page_size": 100}
    tested = {
        call.kwargs["request"]["resource"]
        for call in client.test_iam_permissions.await_args_list
    }
    assert tested == set(names)
    assert checks_by_kind(probe_context)[TOPIC].status is ProbeCheckStatus.SUCCESS


@pytest.mark.asyncio
async def test_probe_stops_discovery_at_one_container_when_nothing_needs_testing(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [FOLDER]
    pager = FakePager([f"folders/{index}" for index in range(8)], page_size=3)
    client = make_client("search_folders", [])
    client.search_folders = AsyncMock(return_value=pager)
    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    assert checks_by_kind(probe_context)[FOLDER].status is ProbeCheckStatus.SUCCESS
    assert pager.pages_served == 1
    assert client.search_folders.await_args.kwargs["request"] == {"page_size": 1}
    client.test_iam_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_probe_counts_errored_containers_against_the_full_total(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", [f"projects/p{index}" for index in range(4)]
    )
    granted = {"projects/p0", "projects/p1"}

    def respond(request: dict[str, Any], **_: Any) -> SimpleNamespace:
        if request["resource"] in granted:
            return SimpleNamespace(permissions=["pubsub.topics.list"])
        raise PermissionDenied("cannot test permissions")

    client.test_iam_permissions = AsyncMock(side_effect=respond)
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert str(check.message).startswith("2 of 4 projects - Could not verify access")


@pytest.mark.asyncio
async def test_probe_reports_denied_and_unverifiable_containers_together(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", [f"projects/p{index}" for index in range(3)]
    )

    def respond(request: dict[str, Any], **_: Any) -> SimpleNamespace:
        if request["resource"] == "projects/p0":
            return SimpleNamespace(permissions=[])
        raise PermissionDenied("cannot test permissions")

    client.test_iam_permissions = AsyncMock(side_effect=respond)
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    # a denial is the actionable verdict, but the unverified containers still count
    assert check.status is ProbeCheckStatus.FAILURE
    assert str(check.message) == (
        "1 of 3 projects - Missing permission(s): pubsub.topics.list (projects/p0)"
        ", and 2 of 3 could not be checked"
    )


@pytest.mark.asyncio
async def test_probe_checks_iam_policy_at_the_project_level(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [IAM_POLICY]
    client = make_client(
        "search_projects",
        ["projects/sandbox"],
        granted=["cloudasset.assets.searchAllIamPolicies"],
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[IAM_POLICY]
    assert check.status is ProbeCheckStatus.SUCCESS
    request: dict[str, Any] = client.test_iam_permissions.await_args.kwargs["request"]
    assert request["permissions"] == ["cloudasset.assets.searchAllIamPolicies"]


@pytest.mark.asyncio
async def test_probe_answers_a_discovery_only_kind_without_testing_it(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # search_projects only returns projects the caller can already get, so the Project
    # kind passes on a container whose testIamPermissions grants nothing at all.
    probe_context.available_kinds = [PROJECT, TOPIC]
    client = make_client("search_projects", ["projects/sandbox"], granted=[])
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.SUCCESS
    assert checks[TOPIC].status is ProbeCheckStatus.FAILURE


@pytest.mark.asyncio
async def test_probe_names_the_containers_when_few_enough_to_act_on(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", [f"projects/p{index}" for index in range(8)]
    )
    denied = {"projects/p5", "projects/p6", "projects/p7"}
    client.test_iam_permissions = AsyncMock(
        side_effect=lambda request, **_: SimpleNamespace(
            permissions=[] if request["resource"] in denied else ["pubsub.topics.list"]
        )
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    assert check.status is ProbeCheckStatus.FAILURE
    assert str(check.message) == (
        "3 of 8 projects - Missing permission(s): pubsub.topics.list "
        "(projects/p5, projects/p6, projects/p7)"
    )


@pytest.mark.asyncio
async def test_a_failed_permission_test_leaves_discovery_answered_kinds_alone(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # testIamPermissions is called for Topic's sake only. Project was already answered
    # by discovery and has nothing to learn from that call failing.
    probe_context.available_kinds = [PROJECT, TOPIC]
    client = make_client("search_projects", ["projects/a", "projects/b"])
    client.test_iam_permissions = AsyncMock(
        side_effect=PermissionDenied("no testIamPermissions")
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.SUCCESS
    assert str(checks[PROJECT].message) == (
        "Permission(s) granted: resourcemanager.projects.get"
    )
    assert checks[TOPIC].status is ProbeCheckStatus.UNKNOWN


@pytest.mark.asyncio
async def test_probe_reports_unknown_when_discovery_fails_without_a_denial(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # the search filters by permission rather than refusing, so a non-denial here is a
    # call that did not complete - telling the user to grant something would be wrong
    probe_context.available_kinds = [FOLDER]
    client = make_client(
        "search_folders", [], search_error=InvalidArgument("bad page token")
    )
    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[FOLDER]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "Could not list GCP folders" in str(check.message)


@pytest.mark.asyncio
async def test_probe_bounds_how_many_containers_are_tested_at_once(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # asyncio.gather schedules every container; the semaphore in _test_container is
    # the only thing keeping an org-sized fan-out off the API
    from gcp_core.helpers.ratelimiter.base import MAXIMUM_CONCURRENT_REQUESTS

    probe_context.available_kinds = [TOPIC]
    names = [f"projects/p{index}" for index in range(MAXIMUM_CONCURRENT_REQUESTS * 3)]
    client = make_client("search_projects", names)
    in_flight = 0
    peak = 0

    async def respond(request: dict[str, Any], **_: Any) -> SimpleNamespace:
        nonlocal in_flight, peak
        in_flight += 1
        peak = max(peak, in_flight)
        await asyncio.sleep(0)
        in_flight -= 1
        return SimpleNamespace(permissions=["pubsub.topics.list"])

    client.test_iam_permissions = AsyncMock(side_effect=respond)
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    assert checks_by_kind(probe_context)[TOPIC].status is ProbeCheckStatus.SUCCESS
    assert client.test_iam_permissions.await_count == len(names)
    assert peak <= MAXIMUM_CONCURRENT_REQUESTS


@pytest.mark.asyncio
async def test_probe_calls_do_not_retry(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # a test connection answers now; the resync retry budget would let one container
    # hold the whole run for minutes
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", ["projects/a"], granted=["pubsub.topics.list"]
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    assert client.search_projects.await_args.kwargs["retry"] is None
    assert client.test_iam_permissions.await_args.kwargs["retry"] is None
    # with retry gone, the per-call timeout is the only thing bounding a run
    from gcp_core.search.paginated_query import DEFAULT_REQUEST_TIMEOUT

    assert (
        client.search_projects.await_args.kwargs["timeout"] == DEFAULT_REQUEST_TIMEOUT
    )
    assert (
        client.test_iam_permissions.await_args.kwargs["timeout"]
        == DEFAULT_REQUEST_TIMEOUT
    )


@pytest.mark.asyncio
async def test_probe_reports_unknown_when_discovery_runs_out_of_retries(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [FOLDER]
    client = make_client("search_folders", [], search_error=RetryError("gave up", None))
    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[FOLDER]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "Could not list GCP folders" in str(check.message)


@pytest.mark.asyncio
async def test_probe_reports_unknown_for_a_container_that_runs_out_of_retries(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [TOPIC]
    client = make_client("search_projects", ["projects/a", "projects/b"])
    client.test_iam_permissions = AsyncMock(side_effect=RetryError("gave up", None))
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[TOPIC]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "Could not verify access" in str(check.message)


@pytest.mark.asyncio
async def test_probe_cancels_sibling_container_tests_before_closing_clients(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # without cancellation the siblings keep running and finish after clients.close()
    probe_context.available_kinds = [TOPIC]
    client = make_client(
        "search_projects", [f"projects/p{index}" for index in range(6)]
    )
    completed: list[str] = []

    async def respond(request: dict[str, Any], **_: Any) -> SimpleNamespace:
        if request["resource"] == "projects/p0":
            raise RuntimeError("boom")
        await asyncio.sleep(0.05)
        completed.append(request["resource"])
        return SimpleNamespace(permissions=["pubsub.topics.list"])

    client.test_iam_permissions = AsyncMock(side_effect=respond)
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)
    await asyncio.sleep(0.2)

    assert probe_context.status is ProbeStatus.FAILED
    assert "RuntimeError" in str(probe_context.message)
    assert completed == []
    assert checks_by_kind(probe_context)[TOPIC].status is ProbeCheckStatus.UNKNOWN


@pytest.mark.asyncio
async def test_probe_reports_an_auth_error_even_when_another_container_fails_first(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    # run() classifies on exception type, so the auth error has to survive the unwrap
    # no matter where it sits in the group
    probe_context.available_kinds = [TOPIC]
    client = make_client("search_projects", ["projects/p0", "projects/p1"])

    async def respond(request: dict[str, Any], **_: Any) -> SimpleNamespace:
        if request["resource"] == "projects/p0":
            raise TypeError("ordered first, unrelated")
        raise GoogleAuthError("credentials expired")

    client.test_iam_permissions = AsyncMock(side_effect=respond)
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    assert probe_context.status is ProbeStatus.FAILED
    assert "Failed to verify GCP authentication" in str(probe_context.message)
    assert "credentials expired" in str(probe_context.message)
