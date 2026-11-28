from datetime import datetime, timedelta, timezone
from itertools import batched
from typing import Any

import httpx
from loguru import logger
from port_ocean.core.incremental.cursor_context import active_incremental_cursor
from port_ocean.exceptions.core import OceanAbortException
from port_ocean.utils.async_http import http_async_client

from gcp_core.cache import cache_coroutine_result
from gcp_core.search.resource_searches import search_projects
from gcp_core.utils import _get_oauth_token

ENTRIES_LIST_URL = "https://logging.googleapis.com/v2/entries:list"

ENTRIES_FIELD_MASK = "entries/logName,nextPageToken"
LOGGING_READ_SCOPE = "https://www.googleapis.com/auth/logging.read"
ACTIVE_PROJECTS_QUERY = "state:ACTIVE"

# entries.list documents a maximum of 100 resource names per request, and a quota of
# 60 requests per minute per calling project and per user, raisable to 200:
# https://cloud.google.com/logging/docs/reference/v2/rest/v2/entries/list
# https://cloud.google.com/logging/quotas
MAX_RESOURCE_NAMES_PER_REQUEST = 100

# The documented default is 50 and no maximum is documented; 1000 and 5000 were both
# accepted against the live API, so this is a conservative choice rather than a limit.
ENTRIES_PAGE_SIZE = 1000

ENTRIES_REQUEST_TIMEOUT = 120.0

CURSOR_OVERLAP = timedelta(minutes=5)

AUDIT_LOG_IDS = (
    "cloudaudit.googleapis.com/activity",
    "cloudaudit.googleapis.com/system_event",
)


def _project_id(project: dict[str, Any]) -> str:
    """The project's own id, under either casing `parse_protobuf_messages` can produce.

    `preserve_api_response_case_style` is a per-block selector, so the key depends on
    which block's selector was active when the listing was parsed. Exactly one is
    always present, so a missing key should fail rather than resolve to nothing.
    """
    if "project_id" in project:
        return str(project["project_id"])
    return str(project["projectId"])


def _entry_project_id(entry: dict[str, Any]) -> str:
    """The project an audit entry belongs to, read off `logName`.

    `logName` is documented Required and formatted `projects/[PROJECT_ID]/logs/[LOG_ID]`,
    with a project number translated to the id, so the second segment always matches the
    listing's `project_id`. `resource.labels.project_id` would be the obvious field and
    is present on every entry measured here, but a monitored resource type is free to
    label its container differently - `compute.googleapis.com/FirewallPolicy` and
    friends carry `resource_container` instead - and a missing label would fail the
    whole sweep.
    """
    return entry["logName"].split("/")[1]


def build_filter(cursor: datetime) -> str:
    """The window to ask about, as a Cloud Logging filter.

    The cursor is converted to UTC before the literal `Z` is stamped on it: it comes
    back from Port through `datetime.fromisoformat` carrying whatever offset was
    echoed, and formatting a `+02:00` time as `Z` would shift the window and
    under-include.
    """
    log_ids = " OR ".join(f'log_id("{log_id}")' for log_id in AUDIT_LOG_IDS)
    window_start = (cursor - CURSOR_OVERLAP).astimezone(timezone.utc)
    return (
        f'( {log_ids} ) AND timestamp>="{window_start.strftime("%Y-%m-%dT%H:%M:%SZ")}"'
    )


async def _post_entries(
    token: str,
    resource_names: list[str],
    log_filter: str,
    page_token: str | None = None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "resourceNames": resource_names,
        "pageSize": ENTRIES_PAGE_SIZE,
        "filter": log_filter,
        "orderBy": "timestamp desc",
    }
    if page_token:
        body["pageToken"] = page_token
    response = await http_async_client.post(
        ENTRIES_LIST_URL,
        params={"fields": ENTRIES_FIELD_MASK},
        json=body,
        headers={"Authorization": f"Bearer {token}"},
        timeout=ENTRIES_REQUEST_TIMEOUT,
        extensions={"retryable": True},
    )
    response.raise_for_status()
    payload: dict[str, Any] = response.json()
    return payload


async def _sweep_batch(token: str, project_ids: list[str], log_filter: str) -> set[str]:
    """Which of `project_ids` have an audit entry in the window.

    `nextPageToken` is the only end-of-results signal `entries.list` documents. A page
    shorter than `ENTRIES_PAGE_SIZE`, an empty one included, is a scan still in
    progress, so page length cannot end the batch without under-including.

    A page that accounts for a project drops it from the next request, which is what
    keeps one chatty project from costing a page-by-page read of the whole window. That
    makes a new query, so the token is dropped with it; a page that accounts for nobody
    carries the token forward instead. Exactly one of the two happens per page, so the
    batch advances on every one of them.

    "Accounted for" is intersected with the names actually asked about, which is what
    makes that guarantee hold: an id this batch did not ask about cannot shrink `unseen`,
    so treating it as progress would re-send the same request forever. It is also what
    keeps the returned set a subset of `project_ids`, so the caller's lookup back to the
    project objects cannot miss.

    A project that does not exist fails the whole request, and the run with it. One the
    service account cannot read is skipped silently unless it is the only name left.
    """
    unseen = set(project_ids)
    seen: set[str] = set()
    page_token: str | None = None
    page = 0

    while unseen:
        page += 1
        try:
            payload = await _post_entries(
                token,
                [f"projects/{project_id}" for project_id in sorted(unseen)],
                log_filter,
                page_token,
            )
        except httpx.HTTPStatusError as rejection:
            logger.error(
                f"Cloud Logging rejected the audit sync of {len(unseen)} project(s) and "
                "returned nothing for any of them, so this incremental run stops here "
                "for every kind, no cursor is advanced, and the next run covers the "
                "same window. The response names the project that caused it: "
                f"{rejection.response.text[:300]}"
            )
            raise

        entries = payload.get("entries", [])
        newly_seen = {_entry_project_id(entry) for entry in entries} & unseen
        seen.update(newly_seen)
        logger.debug(
            f"Audit sync page {page} read {len(entries)} entries and accounted for "
            f"{len(newly_seen)} of the {len(unseen)} project(s) it asked about"
        )

        next_page_token = payload.get("nextPageToken")
        if not next_page_token:
            break
        if newly_seen:
            unseen.difference_update(newly_seen)
            page_token = None
        else:
            page_token = next_page_token

    return seen


@cache_coroutine_result()
async def sweep_changed_projects(cursor: datetime) -> list[dict[str, Any]]:
    """Which projects had audit activity since `cursor`.

    Over-including a project costs one extra re-read of its mapped kinds, which is
    idempotent. Under-including one hides the change until the next full resync, so
    the filter carries no clause that merely makes a change unlikely.
    """
    token = await _get_oauth_token(LOGGING_READ_SCOPE)
    if not token:
        raise OceanAbortException(
            f"Could not obtain a Google access token for {LOGGING_READ_SCOPE}, "
            f"so the audit sync of {ENTRIES_LIST_URL} cannot run"
        )

    projects_by_id = {
        _project_id(project): project
        async for page in search_projects(query=ACTIVE_PROJECTS_QUERY)
        for project in page
    }
    if not projects_by_id:
        logger.warning(
            "No active projects found, so the audit sync has nothing to ask about"
        )
        return []

    log_filter = build_filter(cursor)
    logger.info(
        f"Starting audit sync of {len(projects_by_id)} active project(s) "
        f"with filter {log_filter}"
    )

    changed: set[str] = set()

    for chunk in batched(projects_by_id, MAX_RESOURCE_NAMES_PER_REQUEST):
        changed.update(await _sweep_batch(token, list(chunk), log_filter))

    logger.info(
        f"Audit sync found activity in {len(changed)} of {len(projects_by_id)} project(s)"
    )
    return [projects_by_id[project_id] for project_id in changed]


async def narrow_to_changed_projects() -> list[dict[str, Any]] | None:
    """The projects a fetch should narrow to, or `None` when there is nothing to narrow.

    `None` means a full resync and no narrowing. It is not the same as the empty list,
    which is an incremental run where nothing changed - a distinction the caller has to
    keep, since narrowing to nothing means fetching nothing.

    The sweep itself is cached per cursor in `event.attributes` (`gcp_core/cache.py`),
    which is one dict per event context (`port_ocean/context/event.py:53`) and so lives
    exactly as long as the one `event_context` a run opens.
    """
    cursor = active_incremental_cursor()
    if cursor is None:
        return None
    return await sweep_changed_projects(cursor)
