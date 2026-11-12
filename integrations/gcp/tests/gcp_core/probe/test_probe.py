from types import SimpleNamespace
from collections.abc import Callable
from typing import Any, Generator
from unittest.mock import AsyncMock, MagicMock

import pytest
from google.api_core.exceptions import PermissionDenied
from google.auth.exceptions import DefaultCredentialsError

import port_ocean.context.ocean as ocean_module
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context
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


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    """gcp_core modules read ocean.integration_config at import time."""
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)

    yield

    ocean_module._port_ocean = PortOceanContext(None)


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context


async def run_probe(context: ProbeContext) -> None:
    from gcp_core.probe.probe import GcpPermissionProbe

    await GcpPermissionProbe(context).run()


def make_client(
    search_method: str,
    response_field: str,
    names: list[str],
    granted: list[str] | None = None,
    search_error: Exception | None = None,
) -> MagicMock:
    page = MagicMock()
    setattr(page, response_field, [SimpleNamespace(name=name) for name in names])
    page.next_page_token = ""

    client = MagicMock()
    setattr(
        client,
        search_method,
        (
            AsyncMock(side_effect=search_error)
            if search_error
            else AsyncMock(return_value=page)
        ),
    )
    client.test_iam_permissions = AsyncMock(
        return_value=SimpleNamespace(permissions=granted or [])
    )
    return client


@pytest.fixture
def install_client(monkeypatch: pytest.MonkeyPatch) -> Callable[[str, MagicMock], None]:
    """Pre-populate a singleton slot, as tests/gcp_core/search does."""

    def install(client_name: str, client: MagicMock) -> None:
        import gcp_core.clients as clients

        monkeypatch.setitem(clients._instances, client_name, client)

    return install


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
        "projects",
        ["projects/sandbox"],
        granted=["resourcemanager.projects.get", "pubsub.topics.list"],
    )

    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.SUCCESS
    assert checks[TOPIC].status is ProbeCheckStatus.SUCCESS
    # One call per container, asking for every kind's permissions at that level.
    client.test_iam_permissions.assert_awaited_once()
    request: dict[str, Any] = client.test_iam_permissions.await_args.kwargs["request"]
    assert request["resource"] == "projects/sandbox"
    assert request["permissions"] == [
        "pubsub.topics.list",
        "resourcemanager.projects.get",
    ]


@pytest.mark.asyncio
async def test_probe_fails_only_the_kind_whose_permission_is_missing(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT, TOPIC]
    client = make_client(
        "search_projects",
        "projects",
        ["projects/sandbox"],
        granted=["resourcemanager.projects.get"],
    )

    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    checks = checks_by_kind(probe_context)
    assert checks[PROJECT].status is ProbeCheckStatus.SUCCESS
    assert checks[TOPIC].status is ProbeCheckStatus.FAILURE
    assert "projects/sandbox" in str(checks[TOPIC].message)
    assert "pubsub.topics.list" in str(checks[TOPIC].message)


@pytest.mark.asyncio
async def test_probe_reports_unknown_when_no_folder_is_discovered(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [FOLDER]
    client = make_client("search_folders", "folders", [])

    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[FOLDER]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "No GCP folder was discovered" in str(check.message)
    client.test_iam_permissions.assert_not_awaited()


@pytest.mark.asyncio
async def test_probe_fails_the_kind_when_discovery_is_denied(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [FOLDER]
    client = make_client(
        "search_folders",
        "folders",
        [],
        search_error=PermissionDenied("caller lacks folders.list"),
    )

    install_client("FoldersAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[FOLDER]
    assert check.status is ProbeCheckStatus.FAILURE
    assert "Failed to list GCP folders" in str(check.message)


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
    probe_context.available_kinds = [PROJECT]
    client = make_client(
        "search_projects",
        "projects",
        [],
        search_error=DefaultCredentialsError("no ADC"),
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    assert probe_context.status is ProbeStatus.FAILED
    assert probe_context.message is not None
    assert "Failed to verify GCP authentication" in probe_context.message


@pytest.mark.asyncio
async def test_probe_reports_unknown_when_a_container_check_errors(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT]
    client = make_client("search_projects", "projects", ["projects/sandbox"])
    client.test_iam_permissions = AsyncMock(
        side_effect=PermissionDenied("cannot test permissions")
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[PROJECT]
    assert check.status is ProbeCheckStatus.UNKNOWN
    assert "Could not verify access" in str(check.message)


@pytest.mark.asyncio
async def test_probe_truncates_the_container_list_past_five(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [PROJECT]
    client = make_client(
        "search_projects",
        "projects",
        [f"projects/p{index}" for index in range(8)],
        granted=[],
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[PROJECT]
    assert check.status is ProbeCheckStatus.FAILURE
    assert str(check.message).count("projects/p") == 5
    assert "(and 3 more)" in str(check.message)


@pytest.mark.asyncio
async def test_probe_checks_the_organization_level(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [ORGANIZATION]
    client = make_client(
        "search_organizations",
        "organizations",
        ["organizations/123"],
        granted=["resourcemanager.organizations.get"],
    )
    install_client("OrganizationsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[ORGANIZATION]
    assert check.status is ProbeCheckStatus.SUCCESS
    request = client.test_iam_permissions.await_args.kwargs["request"]
    assert request["resource"] == "organizations/123"
    assert request["permissions"] == ["resourcemanager.organizations.get"]


@pytest.mark.asyncio
async def test_probe_checks_the_custom_kind_slot(
    probe_context: ProbeContext,
    install_client: Callable[[str, MagicMock], None],
) -> None:
    probe_context.available_kinds = [CUSTOM_KIND]
    client = make_client(
        "search_projects",
        "projects",
        ["projects/sandbox"],
        granted=["cloudasset.assets.searchAllResources"],
    )
    install_client("ProjectsAsyncClient", client)

    await run_probe(probe_context)

    check = checks_by_kind(probe_context)[CUSTOM_KIND]
    assert check.status is ProbeCheckStatus.SUCCESS
