from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean

from github.kind.object_kind import ObjectKind
from github.exporters.respository import RepositoryExporter
from github.exporters.issue import IssueExporter
from github.exporters.file import FileExporter
from github.exporters.pull_request import PullRequestExporter


REPOSITORIES: list[str] = []


async def _load_repo_names() -> list[str]:
    """Fetch repositories once and update the global cache."""
    repos = await RepositoryExporter().export()
    repo_names = [
        r["name"]
        for r in repos
        if isinstance(r, dict) and isinstance(r.get("name"), str) and not r["name"].isdigit()
    ]
    globals()["REPOSITORIES"] = repo_names
    logger.info(f"[main] Loaded repositories: {repo_names}")
    return repo_names


@ocean.on_start()
async def on_start() -> None:
    await _load_repo_names()

@ocean.on_resync(ObjectKind.REPOSITORY.value)
async def on_resync_repository(kind: str) -> list[dict[str, Any]]:
    logger.info(f"[main] Resync event received for kind={kind}")
    # Return cached repository entities (names only here; exporter returns full dicts on initial load)
    items = [{"name": name} for name in REPOSITORIES]
    logger.info(f"[main] Resync for kind={kind} returned {len(items)} items.")
    return items


@ocean.on_resync(ObjectKind.ISSUE.value)
async def on_resync_issue(kind: str) -> list[dict[str, Any]]:
    logger.info(f"[main] Resync event received for kind={kind}")
    repo_names = await _load_repo_names()
    items = await IssueExporter(repos=repo_names).export()
    logger.info(f"[main] Resync for kind={kind} returned {len(items)} items.")
    return items


@ocean.on_resync(ObjectKind.FILE.value)
async def on_resync_file(kind: str) -> list[dict[str, Any]]:
    logger.info(f"[main] Resync event received for kind={kind}")
    repo_names = await _load_repo_names()
    items = await FileExporter(repos=repo_names, path="").export()
    logger.info(f"[main] Resync for kind={kind} returned {len(items)} items.")
    return items


@ocean.on_resync(ObjectKind.PULL_REQUEST.value)
async def on_resync_pull_request(kind: str) -> list[dict[str, Any]]:
    logger.info(f"[main] Resync event received for kind={kind}")
    repo_names = await _load_repo_names()
    items = await PullRequestExporter(repos=repo_names).export()
    logger.info(f"[main] Resync for kind={kind} returned {len(items)} items.")
    return items
