import importlib
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import port_ocean.context.ocean as ocean_module
from google.api_core.exceptions import PermissionDenied
from port_ocean.context.event import event_context
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context
from port_ocean.core.incremental.cursor_context import with_active_incremental_cursor
from port_ocean.core.integrations.mixins import EventsMixin

CURSOR = datetime(2026, 11, 26, 9, 15, 0, tzinfo=timezone.utc)

PROJECT = "cloudresourcemanager.googleapis.com/Project"
FOLDER = "cloudresourcemanager.googleapis.com/Folder"
ORGANIZATION = "cloudresourcemanager.googleapis.com/Organization"
TOPIC = "pubsub.googleapis.com/Topic"
SUBSCRIPTION = "pubsub.googleapis.com/Subscription"
CLUSTER = "container.googleapis.com/Cluster"
CLOUD_FUNCTION = "gcpCloudFunction"
CLOUD_RESOURCE = "cloudResource"
IAM_POLICY = "iamPolicy"

CHANGED = {"name": "projects/385573848890", "project_id": "sendbox-go"}
ALSO_CHANGED = {"name": "projects/1", "project_id": "another-project"}


def install_ocean_context(incremental_enabled: bool) -> EventsMixin:
    """A real `EventsMixin` so the decorators register observably and hand back the
    function, as they do in a running integration."""
    integration = EventsMixin()
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.config.integration.incremental_sync_enabled = incremental_enabled
    mock_app.integration = integration
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    return integration


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    install_ocean_context(incremental_enabled=True)
    yield
    ocean_module._port_ocean = PortOceanContext(None)


@pytest.fixture
def gcp_main(mock_ocean_context: None) -> Any:
    """gcp_core modules read ocean.integration_config at import time, so the import has
    to follow the context fixture, as tests/gcp_core/probe does. The reload re-runs the
    decorators against the context this test installed."""
    import main

    return importlib.reload(main)


def single_page(items: list[Any]) -> Any:
    async def _page(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        yield items

    return _page


def _response(entries: list[dict[str, Any]]) -> MagicMock:
    page = MagicMock()
    page.status_code = 200
    page.json.return_value = {"entries": entries}
    page.raise_for_status.return_value = None
    return page


async def collect(
    handler: Any, kind: str, cursor: datetime | None = CURSOR
) -> list[Any]:
    """Drive a handler the way core does: inside an event context, with the kind's
    cursor bound for an incremental run and unbound for a full resync."""
    batches = []
    async with event_context("test_event"):
        if cursor is None:
            async for batch in handler(kind):
                batches.append(batch)
            return batches
        with with_active_incremental_cursor(cursor):
            async for batch in handler(kind):
                batches.append(batch)
    return batches


# --- registration: the decorator order has to survive the flag either way ----------


@pytest.mark.parametrize("incremental_enabled", [True, False])
def test_resync_registration_survives_the_incremental_flag(
    incremental_enabled: bool,
) -> None:
    """`on_resync` returns the function while `on_incremental_resync` returns None when
    the flag is off (`port_ocean/context/ocean.py:150-157`), so incremental has to be
    the outer decorator. Reversed, a flag-off pod would register no resync at all."""
    ocean_module._port_ocean = PortOceanContext(None)
    integration = install_ocean_context(incremental_enabled)

    import main

    importlib.reload(main)

    for kind in (
        FOLDER,
        ORGANIZATION,
        PROJECT,
        TOPIC,
        SUBSCRIPTION,
        CLOUD_FUNCTION,
        CLOUD_RESOURCE,
        IAM_POLICY,
        None,
    ):
        assert integration.event_strategy.resync[kind], f"resync lost {kind}"

    if incremental_enabled:
        assert integration.event_strategy.incremental[None], "catch-all not registered"
        for kind in (PROJECT, TOPIC, SUBSCRIPTION, CLOUD_RESOURCE, IAM_POLICY):
            assert integration.event_strategy.incremental[
                kind
            ], f"no incremental {kind}"
    else:
        assert not integration.event_strategy.incremental


# --- one sweep per run, shared by every kind ---------------------------------------


@pytest.mark.asyncio
async def test_every_kind_in_a_run_sees_one_sweep(gcp_main: Any) -> None:
    """The sweep is cached in `event.attributes`, which is one dict per event context,
    so the kinds of a run share it and a quiet tick is not swept once per kind."""
    from gcp_core.audit_log import narrow_to_changed_projects

    post = AsyncMock(
        return_value=_response(
            [
                {
                    "logName": "projects/sendbox-go/logs/cloudaudit.googleapis.com%2Factivity",
                    "resource": {"labels": {"project_id": "sendbox-go"}},
                }
            ]
        )
    )

    async def listing(query: str | None = None) -> AsyncGenerator[Any, None]:
        yield [CHANGED]

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            with with_active_incremental_cursor(CURSOR):
                for_topics = await narrow_to_changed_projects()
                for_clusters = await narrow_to_changed_projects()
                for_policies = await narrow_to_changed_projects()

    assert post.await_count == 1
    assert for_topics is for_clusters is for_policies
    assert for_topics == [CHANGED]


@pytest.mark.asyncio
async def test_no_cursor_means_no_narrowing_and_no_sweep(gcp_main: Any) -> None:
    from gcp_core.audit_log import narrow_to_changed_projects

    post = AsyncMock()
    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            assert await narrow_to_changed_projects() is None

    post.assert_not_awaited()


# --- per-kind behaviour under a bound cursor ---------------------------------------


@pytest.mark.asyncio
async def test_project_kind_yields_the_objects_the_sweep_already_listed(
    gcp_main: Any,
) -> None:
    """`__project.name` has to stay `projects/<number>`, so the project entities are
    the listed objects rather than ids rebuilt from the audit label."""
    with patch.object(
        gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=[CHANGED])
    ):
        batches = await collect(gcp_main.resync_projects, PROJECT)

    assert batches == [[CHANGED]]


@pytest.mark.asyncio
async def test_project_kind_lists_everything_on_a_full_resync(gcp_main: Any) -> None:
    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=None)
        ),
        patch.object(gcp_main, "search_all_projects", single_page([CHANGED])),
    ):
        batches = await collect(gcp_main.resync_projects, PROJECT, cursor=None)

    assert batches == [[CHANGED]]


def test_kinds_with_no_project_dimension_get_no_incremental_handler(
    gcp_main: Any,
) -> None:
    """The audit sweep signals projects, so folders, organizations and the customer's
    Cloud Function endpoint have nothing to narrow by and register no incremental
    handler of their own. They are still selected as units, because the catch-all under
    `None` matches every block, so each costs one no-op pass per tick: see
    `test_the_catch_all_does_no_work_for_a_kind_it_cannot_serve`."""
    integration = ocean_module._port_ocean.app.integration

    for kind in (FOLDER, ORGANIZATION, CLOUD_FUNCTION):
        assert integration.event_strategy.resync[kind], f"resync lost {kind}"
        assert not integration.event_strategy.incremental[
            kind
        ], f"{kind} has no signal to narrow by"


@pytest.mark.asyncio
async def test_topic_routes_to_the_pubsub_listing_with_the_changed_projects(
    gcp_main: Any,
) -> None:
    """The regression test for deriving the fetch from the kind string: a topic read
    through Cloud Asset Inventory loses `labels`, which the default mapping maps."""
    from gcp_core.search.resource_searches import list_all_topics_per_project

    iterator = MagicMock(return_value=single_page([{"name": "topic"}])())

    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=[CHANGED])
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, None)),
        ),
        patch.object(gcp_main, "iterate_per_available_project", iterator),
    ):
        batches = await collect(gcp_main.resync_topics, TOPIC)

    assert batches == [[{"name": "topic"}]]
    assert iterator.call_args.args[0] is list_all_topics_per_project
    assert iterator.call_args.kwargs["projects"] == [CHANGED]


@pytest.mark.asyncio
async def test_a_cai_kind_is_searched_only_in_the_changed_projects(
    gcp_main: Any,
) -> None:
    from gcp_core.search.resource_searches import search_all_resources

    iterator = MagicMock(return_value=single_page([{"name": "cluster"}])())

    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=[CHANGED])
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "iterate_per_available_project", iterator),
    ):
        await collect(gcp_main.resync_resources, CLUSTER)

    assert iterator.call_args.args[0] is search_all_resources
    assert iterator.call_args.kwargs["projects"] == [CHANGED]


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", [TOPIC, FOLDER, ORGANIZATION, CLOUD_FUNCTION])
async def test_the_catch_all_does_no_work_for_a_kind_it_cannot_serve(
    kind: str, gcp_main: Any
) -> None:
    """Core hands a block the kind's own handlers plus the catch-all, on an incremental
    run exactly as on a resync, so the catch-all has to stand aside for every kind in
    `AssetTypesWithSpecialHandling` - the ones with their own handler and the three
    with no incremental handler at all. It yields nothing and fetches nothing; the cost
    of the pass is the cursor write core does afterwards."""
    iterator = MagicMock()
    listing = MagicMock()

    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=[CHANGED])
        ),
        patch.object(gcp_main, "iterate_per_available_project", iterator),
        patch.object(gcp_main, "search_all_folders", listing),
        patch.object(gcp_main, "search_all_organizations", listing),
        patch.object(gcp_main, "resync_cloud_function_resources", listing),
    ):
        batches = await collect(gcp_main.resync_resources, kind)

    assert batches == []
    iterator.assert_not_called()
    listing.assert_not_called()


@pytest.mark.asyncio
async def test_iam_policy_reads_the_same_changed_projects_as_every_other_kind(
    gcp_main: Any,
) -> None:
    """There is no narrower IAM set: a binding can change without a `SetIamPolicy`
    entry - `storage.setIamPermissions` and a deleted principal both do - so any
    marker-based narrowing would under-include, which is the expensive direction."""
    iterator = MagicMock(return_value=single_page([{"policy": "binding"}])())

    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=[CHANGED])
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "get_current_resource_config", MagicMock()),
        patch.object(gcp_main, "iterate_per_available_project", iterator),
    ):
        batches = await collect(gcp_main.resync_iam_policies, IAM_POLICY)

    assert batches == [[{"policy": "binding"}]]
    assert iterator.call_args.kwargs["projects"] == [CHANGED]


@pytest.mark.asyncio
async def test_iam_policy_skips_one_permission_denied_project_when_incremental(
    gcp_main: Any,
) -> None:
    """The fetch re-raises `PermissionDenied` to protect a resync's delete phase. An
    incremental run has no delete phase, and a raise here would skip every block the
    customer ordered after this one."""

    async def denied(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        yield [{"policy": "from-a-readable-project"}]
        raise ExceptionGroup("one project failed", [PermissionDenied("no access")])

    with (
        patch.object(
            gcp_main,
            "narrow_to_changed_projects",
            AsyncMock(return_value=[CHANGED, ALSO_CHANGED]),
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "get_current_resource_config", MagicMock()),
        patch.object(gcp_main, "iterate_per_available_project", denied),
    ):
        batches = await collect(gcp_main.resync_iam_policies, IAM_POLICY)

    assert batches == [[{"policy": "from-a-readable-project"}]]


@pytest.mark.asyncio
async def test_iam_policy_still_raises_permission_denied_on_a_full_resync(
    gcp_main: Any,
) -> None:
    """A resync does have a delete phase, so the raise has to survive there."""

    async def denied(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        yield []
        raise ExceptionGroup("one project failed", [PermissionDenied("no access")])

    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=None)
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "get_current_resource_config", MagicMock()),
        patch.object(gcp_main, "iterate_per_available_project", denied),
    ):
        with pytest.raises(ExceptionGroup):
            await collect(gcp_main.resync_iam_policies, IAM_POLICY, cursor=None)


@pytest.mark.asyncio
async def test_iam_policy_still_fails_on_any_other_error(gcp_main: Any) -> None:
    async def mixed(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        yield []
        raise ExceptionGroup(
            "two projects failed",
            [PermissionDenied("no access"), RuntimeError("something else")],
        )

    with (
        patch.object(
            gcp_main,
            "narrow_to_changed_projects",
            AsyncMock(return_value=[CHANGED, ALSO_CHANGED]),
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "get_current_resource_config", MagicMock()),
        patch.object(gcp_main, "iterate_per_available_project", mixed),
    ):
        with pytest.raises(ExceptionGroup) as raised:
            await collect(gcp_main.resync_iam_policies, IAM_POLICY)

    assert RuntimeError in [type(error) for error in raised.value.exceptions]


@pytest.mark.asyncio
async def test_iam_policy_still_fails_on_an_other_error_nested_in_a_group(
    gcp_main: Any,
) -> None:
    """Counting a group's direct children would call this all-denied and swallow it.

    The fan-out raises one flat group today, so this shape only arrives the day it
    groups errors per page instead. `split` is right either way.
    """

    async def nested(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        yield []
        raise ExceptionGroup(
            "one page failed",
            [
                ExceptionGroup(
                    "two projects failed",
                    [PermissionDenied("no access"), RuntimeError("something else")],
                )
            ],
        )

    with (
        patch.object(
            gcp_main,
            "narrow_to_changed_projects",
            AsyncMock(return_value=[CHANGED, ALSO_CHANGED]),
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "get_current_resource_config", MagicMock()),
        patch.object(gcp_main, "iterate_per_available_project", nested),
    ):
        with pytest.raises(ExceptionGroup) as raised:
            await collect(gcp_main.resync_iam_policies, IAM_POLICY)

    assert RuntimeError in [
        type(error) for error in raised.value.exceptions[0].exceptions
    ]


@pytest.mark.asyncio
async def test_a_full_resync_narrows_nothing_and_sweeps_nothing(gcp_main: Any) -> None:
    """The second decorator must not change the resync path: with no cursor bound,
    `projects` is None, which is the parameter's default, so the iterator falls back to
    `search_all_projects()` exactly as before."""
    iterator = MagicMock(return_value=single_page([{"name": "topic"}])())
    post = AsyncMock()

    with (
        patch("gcp_core.audit_log.http_async_client.post", post),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, None)),
        ),
        patch.object(gcp_main, "iterate_per_available_project", iterator),
    ):
        batches = await collect(gcp_main.resync_topics, TOPIC, cursor=None)

    assert batches == [[{"name": "topic"}]]
    assert iterator.call_args.kwargs["projects"] is None
    post.assert_not_awaited()


@pytest.mark.asyncio
async def test_the_project_arm_of_the_dispatch_narrows_too(gcp_main: Any) -> None:
    """A `cloudResource` block can name `…/Project` as a sub-kind, which routes through
    the dispatch rather than `resync_projects`. Both paths narrow, so the same asset
    type cannot behave differently depending on which block declared it."""
    async with event_context("test_event"):
        iterator = await gcp_main._resolve_resync_method_for_resource(
            PROJECT, projects=[CHANGED]
        )
        batches = [batch async for batch in iterator]

    assert batches == [[CHANGED]]


@pytest.mark.asyncio
async def test_the_project_arm_of_the_dispatch_lists_everything_on_a_full_resync(
    gcp_main: Any,
) -> None:
    """The counterpart to the narrowing case: with no project list the arm returns the
    cached full listing, exactly as it does on main."""
    with patch.object(gcp_main, "search_all_projects", single_page([CHANGED])):
        async with event_context("test_event"):
            iterator = await gcp_main._resolve_resync_method_for_resource(PROJECT)
            batches = [batch async for batch in iterator]

    assert batches == [[CHANGED]]


@pytest.mark.asyncio
async def test_iam_policy_continues_when_the_only_changed_project_denies(
    gcp_main: Any,
) -> None:
    """An incremental run fans out over the projects that changed, often one. Failing
    the kind on "every project denied" would therefore fail on a single denial and skip
    every block the customer ordered after it."""

    async def denied(*args: Any, **kwargs: Any) -> AsyncGenerator[Any, None]:
        raise ExceptionGroup("the only project failed", [PermissionDenied("no access")])
        yield []  # pragma: no cover - unreachable, keeps this an async generator

    with (
        patch.object(
            gcp_main, "narrow_to_changed_projects", AsyncMock(return_value=[CHANGED])
        ),
        patch.object(
            gcp_main,
            "resolve_request_controllers",
            AsyncMock(return_value=(None, MagicMock())),
        ),
        patch.object(gcp_main, "get_current_resource_config", MagicMock()),
        patch.object(gcp_main, "iterate_per_available_project", denied),
    ):
        batches = await collect(gcp_main.resync_iam_policies, IAM_POLICY)

    assert batches == []
