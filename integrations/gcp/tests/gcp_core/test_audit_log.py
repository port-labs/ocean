from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
import port_ocean.context.ocean as ocean_module
from port_ocean.context.event import event_context
from port_ocean.context.ocean import PortOceanContext, initialize_port_ocean_context

CURSOR = datetime(2026, 11, 26, 9, 15, 0, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def mock_ocean_context() -> Generator[None, None, None]:
    mock_app = MagicMock()
    mock_app.config.integration.config = {"search_all_resources_per_minute_quota": 100}
    mock_app.cache_provider = AsyncMock()
    mock_app.cache_provider.get.return_value = None
    initialize_port_ocean_context(mock_app)
    yield
    ocean_module._port_ocean = PortOceanContext(None)


@pytest.fixture
def audit_log(mock_ocean_context: None) -> Any:
    """gcp_core modules read ocean.integration_config at import time, so the import
    has to follow the context fixture, as tests/gcp_core/probe does."""
    import gcp_core.audit_log

    return gcp_core.audit_log


def project(project_id: str, number: str, id_key: str = "project_id") -> dict[str, Any]:
    return {"name": f"projects/{number}", id_key: project_id, "state": "ACTIVE"}


def entry(project_id: str, severity: str = "NOTICE") -> dict[str, Any]:
    return {
        "logName": f"projects/{project_id}/logs/cloudaudit.googleapis.com%2Factivity",
        "resource": {"type": "audited_resource", "labels": {"project_id": project_id}},
        "severity": severity,
    }


def entry_without_a_project_label(project_id: str) -> dict[str, Any]:
    """A monitored resource type is free to label its container differently:
    `compute.googleapis.com/FirewallPolicy` and friends carry `resource_container`."""
    return {
        "logName": f"projects/{project_id}/logs/cloudaudit.googleapis.com%2Factivity",
        "resource": {
            "type": "compute.googleapis.com/FirewallPolicy",
            "labels": {"resource_container": f"projects/{project_id}"},
        },
        "severity": "NOTICE",
    }


def response(
    entries: list[dict[str, Any]], next_page_token: str | None = None
) -> MagicMock:
    page = MagicMock(spec=httpx.Response)
    page.status_code = 200
    body: dict[str, Any] = {"entries": entries}
    if next_page_token:
        body["nextPageToken"] = next_page_token
    page.json.return_value = body
    page.raise_for_status.return_value = None
    return page


def not_found_response(resource: str) -> MagicMock:
    page = MagicMock(spec=httpx.Response)
    page.status_code = 404
    page.text = (
        f'{{"error": {{"code": 404, "message": "{resource} does not exist", '
        '"status": "NOT_FOUND"}}'
    )
    page.json.return_value = {
        "error": {
            "code": 404,
            "message": f"{resource} does not exist",
            "details": [
                {
                    "@type": "type.googleapis.com/google.rpc.ErrorInfo",
                    "reason": "QUERY_INVALID_RESOURCE_NAME",
                    "domain": "logging.googleapis.com",
                    "metadata": {"resource": resource},
                }
            ],
        }
    }
    page.raise_for_status.side_effect = httpx.HTTPStatusError(
        "404", request=MagicMock(), response=page
    )
    return page


def listing(projects: list[dict[str, Any]]) -> Any:
    async def _listing(query: str | None = None) -> AsyncGenerator[Any, None]:
        yield projects

    return _listing


def test_build_filter_reads_both_audit_logs_and_carries_no_severity_clause(
    audit_log: Any,
) -> None:
    log_filter = audit_log.build_filter(CURSOR)

    assert 'log_id("cloudaudit.googleapis.com/activity")' in log_filter
    assert 'log_id("cloudaudit.googleapis.com/system_event")' in log_filter
    assert "severity" not in log_filter


def test_build_filter_starts_the_window_before_the_cursor(audit_log: Any) -> None:
    assert (
        f'timestamp>="{(CURSOR - audit_log.CURSOR_OVERLAP).strftime("%Y-%m-%dT%H:%M:%SZ")}"'
        in audit_log.build_filter(CURSOR)
    )


@pytest.mark.asyncio
async def test_an_empty_sweep_is_cached_rather_than_repeated_per_kind(
    audit_log: Any,
) -> None:
    """A quiet tick is the case this sweep exists for, and `cache_coroutine_result`
    decides a hit by membership, so the empty answer is cached like any other."""
    post = AsyncMock(return_value=response([]))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing([project("quiet", "1")])),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            first = await audit_log.sweep_changed_projects(CURSOR)
            second = await audit_log.sweep_changed_projects(CURSOR)

    assert first == [] and second == []
    assert post.await_count == 1


@pytest.mark.asyncio
async def test_sweep_returns_only_the_projects_that_had_activity(
    audit_log: Any,
) -> None:
    projects = [project("quiet", "1"), project("busy", "2"), project("also-busy", "3")]
    post = AsyncMock(return_value=response([entry("busy"), entry("also-busy")]))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert {p["project_id"] for p in changed} == {"busy", "also-busy"}


@pytest.mark.asyncio
async def test_sweep_reads_the_project_off_logname_not_the_resource_label(
    audit_log: Any,
) -> None:
    """`logName` is documented Required and carries the id; a resource label is not
    guaranteed, and a missing one would fail the whole sweep."""
    post = AsyncMock(
        return_value=response([entry_without_a_project_label("firewalled")])
    )

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch(
            "gcp_core.audit_log.search_projects", listing([project("firewalled", "1")])
        ),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert [p["project_id"] for p in changed] == ["firewalled"]


@pytest.mark.asyncio
async def test_sweep_keeps_an_error_severity_entry(audit_log: Any) -> None:
    """There is no severity clause: an over-included project costs one re-read, an
    under-included one costs staleness until the full resync."""
    post = AsyncMock(return_value=response([entry("failed-call", severity="ERROR")]))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch(
            "gcp_core.audit_log.search_projects", listing([project("failed-call", "1")])
        ),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert [p["project_id"] for p in changed] == ["failed-call"]


@pytest.mark.asyncio
async def test_sweep_lists_only_active_projects(audit_log: Any) -> None:
    queries: list[str | None] = []

    async def recording_listing(query: str | None = None) -> AsyncGenerator[Any, None]:
        queries.append(query)
        yield [project("one", "1")]

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", recording_listing),
        patch(
            "gcp_core.audit_log.http_async_client.post",
            AsyncMock(return_value=response([])),
        ),
    ):
        async with event_context("test_event"):
            await audit_log.sweep_changed_projects(CURSOR)

    assert queries == [audit_log.ACTIVE_PROJECTS_QUERY]


@pytest.mark.asyncio
async def test_sweep_chunks_resource_names_at_the_documented_maximum(
    audit_log: Any,
) -> None:
    projects = [project(f"p{index}", str(index)) for index in range(250)]
    post = AsyncMock(return_value=response([]))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            await audit_log.sweep_changed_projects(CURSOR)

    chunk_sizes = [
        len(call.kwargs["json"]["resourceNames"]) for call in post.await_args_list
    ]
    assert chunk_sizes == [audit_log.MAX_RESOURCE_NAMES_PER_REQUEST, 100, 50]
    assert post.await_args_list[0].kwargs["json"]["resourceNames"][0] == "projects/p0"


@pytest.mark.asyncio
async def test_sweep_fails_the_run_and_names_the_nonexistent_project(
    audit_log: Any,
) -> None:
    """Measured: a project that does not exist fails the whole request and nothing is
    salvageable. The cursor is not saved, and the next run's `state:ACTIVE` listing no
    longer returns it."""
    post = AsyncMock(return_value=not_found_response("projects/gone"))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing([project("gone", "1")])),
        patch("gcp_core.audit_log.http_async_client.post", post),
        patch("gcp_core.audit_log.logger") as mock_logger,
    ):
        async with event_context("test_event"):
            with pytest.raises(httpx.HTTPStatusError):
                await audit_log.sweep_changed_projects(CURSOR)

    assert post.await_count == 1
    assert "projects/gone" in str(mock_logger.error.call_args)


@pytest.mark.asyncio
async def test_an_unreadable_project_is_indistinguishable_from_a_quiet_one(
    audit_log: Any,
) -> None:
    """Measured against the live API: asking about a readable and an unreadable project
    together returns 200 with only the readable one's entries. There is no rejection to
    react to, so a missing grant looks exactly like no activity."""
    post = AsyncMock(return_value=response([entry("readable")]))
    projects = [project("readable", "1"), project("unreadable", "2")]

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert [p["project_id"] for p in changed] == ["readable"]


@pytest.mark.asyncio
async def test_sweep_asks_for_a_partial_response(audit_log: Any) -> None:
    """The sweep reads `logName` and nothing else, so a full AuditLog payload is ~24x
    the bytes. A partial response returns only the fields the mask names, so the mask
    has to name `nextPageToken` too - it is the signal `_sweep_batch` terminates on."""
    post = AsyncMock(return_value=response([entry("one")]))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing([project("one", "1")])),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            await audit_log.sweep_changed_projects(CURSOR)

    assert (
        post.await_args_list[0].kwargs["params"]["fields"]
        == "entries/logName,nextPageToken"
    )


@pytest.mark.asyncio
async def test_sweep_opts_the_post_into_transport_retries(audit_log: Any) -> None:
    """The transport retries idempotent methods only, so a POST opts in by hand. A 429
    that propagates fails the kind, which widens the next window and makes the retry
    more expensive than the attempt that failed."""
    post = AsyncMock(return_value=response([entry("one")]))

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing([project("one", "1")])),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            await audit_log.sweep_changed_projects(CURSOR)

    assert post.await_args_list[0].kwargs["extensions"] == {"retryable": True}


@pytest.mark.asyncio
async def test_a_noisy_project_does_not_hide_the_others(audit_log: Any) -> None:
    """One project filling a whole page must not cost the batch its other projects, and
    must not cost it a page-by-page read of the window either: the next round asks only
    about the projects still unaccounted for."""
    projects = [project("noisy", "1"), project("quiet-ish", "2"), project("quiet", "3")]
    full_page = response([entry("noisy")] * 3, next_page_token="more-noise")
    second_round = response([entry("quiet-ish")])
    post = AsyncMock(side_effect=[full_page, second_round])

    with (
        patch("gcp_core.audit_log.ENTRIES_PAGE_SIZE", 3),
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert {p["project_id"] for p in changed} == {"noisy", "quiet-ish"}
    assert post.await_count == 2
    assert post.await_args_list[0].kwargs["json"]["resourceNames"] == [
        "projects/noisy",
        "projects/quiet",
        "projects/quiet-ish",
    ]
    assert post.await_args_list[1].kwargs["json"]["resourceNames"] == [
        "projects/quiet",
        "projects/quiet-ish",
    ]


@pytest.mark.asyncio
async def test_rounds_are_bounded_by_projects_not_by_entry_volume(
    audit_log: Any,
) -> None:
    """Every name in a request is one not yet seen, so a page that reports more results
    still moves at least one project from unseen to seen, and the token it reports is
    dropped with the query it belongs to. Three projects, one per page: three rounds."""
    projects = [project(f"p{index}", str(index)) for index in range(3)]
    post = AsyncMock(
        side_effect=[
            response([entry("p0")], next_page_token="after-p0"),
            response([entry("p1")], next_page_token="after-p1"),
            response([entry("p2")]),
        ]
    )

    with (
        patch("gcp_core.audit_log.ENTRIES_PAGE_SIZE", 1),
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert {p["project_id"] for p in changed} == {"p0", "p1", "p2"}
    assert post.await_count == 3


@pytest.mark.asyncio
async def test_a_403_fails_the_run(audit_log: Any) -> None:
    """Measured: a request whose names the service account cannot read answers 403.
    Nothing is salvageable, so the cursor stays where it is and the failure is loud."""
    forbidden = MagicMock(spec=httpx.Response)
    forbidden.status_code = 403
    forbidden.text = "permission denied"
    forbidden.json.return_value = {"error": {"code": 403, "message": "denied"}}
    forbidden.raise_for_status.side_effect = httpx.HTTPStatusError(
        "403", request=MagicMock(), response=forbidden
    )

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing([project("one", "1")])),
        patch(
            "gcp_core.audit_log.http_async_client.post",
            AsyncMock(return_value=forbidden),
        ),
    ):
        async with event_context("test_event"):
            with pytest.raises(httpx.HTTPStatusError):
                await audit_log.sweep_changed_projects(CURSOR)


@pytest.mark.asyncio
async def test_a_short_page_that_reports_more_results_does_not_end_the_batch(
    audit_log: Any,
) -> None:
    """`entries.list` documents that a page carrying `nextPageToken` may hold fewer
    entries than `pageSize` - none at all - because the scan is still in progress. Page
    length is therefore not an end-of-results signal: treating it as one reports the
    project quiet, advances the cursor and loses the change until the next full resync.

    Nothing was found on the first page, so the second asks the same question with the
    token rather than re-narrowing."""
    projects = [project("changed", "1"), project("quiet", "2")]
    still_scanning = response([], next_page_token="keep-going")
    the_entry = response([entry("changed")])
    post = AsyncMock(side_effect=[still_scanning, the_entry])

    with (
        patch("gcp_core.audit_log.ENTRIES_PAGE_SIZE", 50),
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert {p["project_id"] for p in changed} == {"changed"}
    assert post.await_count == 2
    assert "pageToken" not in post.await_args_list[0].kwargs["json"]
    assert post.await_args_list[1].kwargs["json"]["pageToken"] == "keep-going"
    assert post.await_args_list[1].kwargs["json"]["resourceNames"] == [
        "projects/changed",
        "projects/quiet",
    ]


@pytest.mark.asyncio
async def test_an_entry_for_a_project_the_batch_did_not_ask_about_is_ignored(
    audit_log: Any,
) -> None:
    """`logName` is documented to carry the project id, but it is read off a string from
    a second API and the batch's own contract is "which of `project_ids`". An id outside
    that set cannot shrink `unseen`, so counting it as progress would discard the page
    token and re-send the same request forever, and carrying it into the result would
    fail the caller's lookup back to the project objects."""
    projects = [project("asked", "1")]
    stranger = response([entry("never-asked-about")], next_page_token="keep-going")
    the_entry = response([entry("asked")])
    post = AsyncMock(side_effect=[stranger, the_entry])

    with (
        patch("gcp_core.audit_log._get_oauth_token", AsyncMock(return_value="token")),
        patch("gcp_core.audit_log.search_projects", listing(projects)),
        patch("gcp_core.audit_log.http_async_client.post", post),
    ):
        async with event_context("test_event"):
            changed = await audit_log.sweep_changed_projects(CURSOR)

    assert {p["project_id"] for p in changed} == {"asked"}
    assert post.await_count == 2
    assert post.await_args_list[1].kwargs["json"]["pageToken"] == "keep-going"
