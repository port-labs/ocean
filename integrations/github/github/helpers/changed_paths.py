"""Paths changed on a branch since a point in time, for the file-based kinds.

The base is the branch tip at ``since``: the commit the newest push at or before
``since`` left the branch on, taken from the repository's push activity (push
time, not commit time, so commits created earlier but pushed later are included).
It is compared with the branch's current tip, so pushes the activity doesn't show
yet are still in the compare. ``None`` means the changes can't be trusted, and the
caller reads every matching path in the repository instead.
"""

from datetime import datetime
from typing import Optional
from urllib.parse import quote

import httpx
from loguru import logger
from port_ocean.utils.cache import cache_coroutine_result
from port_ocean.utils.time import convert_str_to_utc_datetime

from github.clients.http.rest_client import GithubRestClient

GIT_NULL_SHA = "0" * 40
# Compare statuses where the base is an ancestor of the branch tip (the branch only
# moved forward), so the compare holds every change made since the base.
FAST_FORWARD_COMPARE_STATUSES = {"ahead", "identical"}
# GitHub's commit compare lists at most 300 files and doesn't say when it cut the list.
COMMIT_COMPARE_MAX_FILES = 300


@cache_coroutine_result()
async def changed_paths_since(
    client: GithubRestClient,
    organization: str,
    repo_name: str,
    branch: str,
    since: Optional[datetime],
) -> Optional[list[str]]:
    """Paths added or modified on ``branch`` since ``since``.

    None when they are unknown: there is no ``since``, or the changes can't be
    trusted. Either way the caller keeps every path.
    Deleted paths are left out: there is no file to fetch for them, and the next
    full resync removes their entities.
    """
    if since is None:
        return None
    repo = f"{organization}/{repo_name}@{branch}"
    try:
        base_sha = await _branch_tip_at(client, organization, repo_name, branch, since)
        if base_sha is None:
            logger.info(f"Branch tip of {repo} at {since.isoformat()} is unknown")
            return None
        return await _changed_paths_from(
            client, organization, repo_name, branch, base_sha
        )
    except httpx.HTTPError as err:
        logger.warning(f"Failed to read changes of {repo}: {err}")
        return None


async def _branch_tip_at(
    client: GithubRestClient,
    organization: str,
    repo_name: str,
    branch: str,
    since: datetime,
) -> Optional[str]:
    """The commit ``branch`` pointed to at ``since``, from its push activity.

    Activity is listed newest first, so the first entry at or before ``since`` set
    the tip in effect then, and later pages are never requested. None when the
    activity doesn't reach back to ``since`` (or isn't available), or the branch
    didn't exist then.
    """
    async for activities in client.send_paginated_request(
        f"{client.base_url}/repos/{organization}/{repo_name}/activity",
        params={"ref": branch, "direction": "desc"},
    ):
        for activity in activities:
            if convert_str_to_utc_datetime(activity["timestamp"]) > since:
                continue
            tip = activity.get("after")
            if not tip or tip == GIT_NULL_SHA:
                return None
            return tip
    return None


async def _changed_paths_from(
    client: GithubRestClient,
    organization: str,
    repo_name: str,
    branch: str,
    base_sha: str,
) -> Optional[list[str]]:
    """Paths added or modified between ``base_sha`` and ``branch``'s tip; None when the compare is incomplete."""
    repo = f"{organization}/{repo_name}@{branch}"
    compare = await client.send_api_request(
        f"{client.base_url}/repos/{organization}/{repo_name}/compare/{base_sha}...{quote(branch)}"
    )
    # A 404 comes back as {}, which has no status either.
    if compare.get("status") not in FAST_FORWARD_COMPARE_STATUSES:
        logger.info(f"History of {repo} was rewritten or is unreadable")
        return None
    files = compare.get("files", [])
    if len(files) >= COMMIT_COMPARE_MAX_FILES:
        logger.info(f"Compare of {repo} may be cut off at {len(files)} files")
        return None

    paths = [file["filename"] for file in files if file.get("status") != "removed"]
    logger.info(f"Found {len(paths)} changed paths in {repo}")
    return paths


def ancestor_dirs(paths: list[str]) -> set[str]:
    """Every folder containing one of ``paths``: ``a/b/c.txt`` -> ``{"a", "a/b"}``."""
    dirs: set[str] = set()
    for path in paths:
        parts = path.split("/")[:-1]
        dirs.update("/".join(parts[:depth]) for depth in range(1, len(parts) + 1))
    return dirs
