import importlib
import sys
from collections.abc import AsyncGenerator, Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from types import ModuleType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.incremental.cursor_context import (
    with_active_incremental_cursor,
)

from github.helpers.utils import ObjectKind

CURSOR = datetime(2026, 11, 15, 10, 0, tzinfo=timezone.utc)
ORG = {"login": "test-org", "type": "Organization"}
REPOS = [{"name": "repo-a"}, {"name": "repo-b"}]


def _passthrough(function: Any, kind: str | None = None) -> Any:
    return function


@pytest.fixture
def main_module() -> tuple[ModuleType, MagicMock]:
    """Import main with resync decorators returning the real handlers."""
    on_incremental_resync = MagicMock(side_effect=_passthrough)
    with (
        patch(
            "port_ocean.context.ocean.ocean.integration.on_resync",
            side_effect=_passthrough,
        ),
        patch(
            "port_ocean.context.ocean.ocean.integration.on_incremental_resync",
            on_incremental_resync,
        ),
        patch(
            "port_ocean.context.ocean.ocean.app.config.integration.incremental_sync_enabled",
            True,
        ),
    ):
        main = (
            importlib.reload(sys.modules["main"])
            if "main" in sys.modules
            else importlib.import_module("main")
        )
    return main, on_incremental_resync


class FakeRepositoryExporter:
    calls: list[dict[str, Any]] = []

    def __init__(self, client: Any) -> None:
        pass

    async def get_paginated_resources(
        self, options: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        FakeRepositoryExporter.calls.append(dict(options))
        yield REPOS


class FakeOrganizationExporter:
    def __init__(self, client: Any) -> None:
        pass

    async def get_paginated_resources(
        self, options: Any = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [ORG]


def _fake_repo_child_exporter(
    items_per_repo: Callable[[str], list[dict[str, Any]]],
) -> type:
    class FakeExporter:
        def __init__(self, client: Any) -> None:
            pass

        async def get_paginated_resources(
            self, options: dict[str, Any]
        ) -> AsyncGenerator[list[dict[str, Any]], None]:
            yield items_per_repo(options["repo_name"])

    return FakeExporter


def _patch_common(main: ModuleType, monkeypatch: pytest.MonkeyPatch) -> None:
    FakeRepositoryExporter.calls = []
    auth_provider = MagicMock()
    auth_provider.list_authenticators = AsyncMock(return_value=[MagicMock()])
    monkeypatch.setattr(main, "get_auth_provider", lambda: auth_provider)
    monkeypatch.setattr(main, "create_github_client", lambda *_: MagicMock())
    monkeypatch.setattr(main, "RestOrganizationExporter", FakeOrganizationExporter)
    monkeypatch.setattr(main, "RestRepositoryExporter", FakeRepositoryExporter)

    resource_config = MagicMock()
    resource_config.selector.repo_search = None
    resource_config.selector.exclude_archived = False
    port_app_config = MagicMock(repository_type="all")
    monkeypatch.setattr(
        main,
        "event",
        MagicMock(resource_config=resource_config, port_app_config=port_app_config),
    )


async def _collect(generator: AsyncGenerator[list[dict[str, Any]], None]) -> list[Any]:
    return [item async for batch in generator for item in batch]


def _tags(repo_name: str) -> list[dict[str, Any]]:
    return [{"name": f"{repo_name}-v1"}, {"name": f"{repo_name}-v2"}]


def _branches(repo_name: str) -> list[dict[str, Any]]:
    return [{"name": "main", "repo": repo_name}, {"name": "dev", "repo": repo_name}]


def _workflows(repo_name: str) -> list[dict[str, Any]]:
    return [{"id": f"{repo_name}-ci", "updated_at": "2020-01-01T00:00:00Z"}]


@contextmanager
def _sync(cursor: datetime | None) -> Iterator[None]:
    """A full resync when *cursor* is None, otherwise an incremental one."""
    if cursor is None:
        yield
        return
    with with_active_incremental_cursor(cursor):
        yield


@pytest.mark.parametrize(
    "kind", [ObjectKind.TAG, ObjectKind.WORKFLOW, ObjectKind.BRANCH, ObjectKind.PLUGIN]
)
def test_registered_for_incremental_resync(
    main_module: tuple[ModuleType, MagicMock], kind: ObjectKind
) -> None:
    _, on_incremental_resync = main_module
    registered_kinds = [c.args[1] for c in on_incremental_resync.call_args_list]
    assert kind in registered_kinds


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", [None, CURSOR], ids=["full", "incremental"])
@pytest.mark.parametrize(
    ("handler_name", "exporter_name", "items_per_repo", "kind"),
    [
        ("resync_tags", "RestTagExporter", _tags, ObjectKind.TAG),
        ("resync_workflows", "RestWorkflowExporter", _workflows, ObjectKind.WORKFLOW),
        ("resync_branches", "RestBranchExporter", _branches, ObjectKind.BRANCH),
    ],
)
async def test_resync_lists_repos_pushed_since_cursor(
    main_module: tuple[ModuleType, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
    cursor: datetime | None,
    handler_name: str,
    exporter_name: str,
    items_per_repo: Callable[[str], list[dict[str, Any]]],
    kind: ObjectKind,
) -> None:
    main, _ = main_module
    _patch_common(main, monkeypatch)
    monkeypatch.setattr(main, exporter_name, _fake_repo_child_exporter(items_per_repo))

    with _sync(cursor):
        items = await _collect(getattr(main, handler_name)(kind))

    assert FakeRepositoryExporter.calls[0]["pushed_since"] == cursor
    # No timestamp filtering below the repo level: every item of a selected repo
    # is returned, even workflows whose updated_at predates the cursor.
    assert sorted(items, key=str) == sorted(
        items_per_repo("repo-a") + items_per_repo("repo-b"), key=str
    )


class FakeRepositorySelector:
    calls: list[datetime | None] = []

    def __init__(self, repo_type: str) -> None:
        pass

    async def select_repos(
        self,
        selector: Any,
        repo_exporter: Any,
        org_login: str,
        org_type: str,
        *,
        pushed_since: datetime | None = None,
    ) -> AsyncGenerator[tuple[str, str, dict[str, Any]], None]:
        FakeRepositorySelector.calls.append(pushed_since)
        for repo in REPOS:
            yield repo["name"], "main", repo


class FakePluginExporter:
    def __init__(self, client: Any, providers: Any, max_depth: Any = None) -> None:
        pass

    async def get_paginated_resources(
        self, options: dict[str, Any]
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        yield [
            {"plugin": "p", "repo": repo["repository"]["name"]}
            for repo in options["repositories"]
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("cursor", [None, CURSOR], ids=["full", "incremental"])
async def test_plugin_resync_selects_repos_pushed_since_cursor(
    main_module: tuple[ModuleType, MagicMock],
    monkeypatch: pytest.MonkeyPatch,
    cursor: datetime | None,
) -> None:
    main, _ = main_module
    _patch_common(main, monkeypatch)
    FakeRepositorySelector.calls = []
    monkeypatch.setattr(main, "CompositeRepositorySelector", FakeRepositorySelector)
    monkeypatch.setattr(main, "PluginExporter", FakePluginExporter)
    monkeypatch.setattr(main, "can_access_organization", lambda *_: True)
    main.event.resource_config.selector.paths = [MagicMock(organization="test-org")]

    with _sync(cursor):
        plugins = await _collect(main.resync_plugins(ObjectKind.PLUGIN))

    assert FakeRepositorySelector.calls == [cursor]
    # Plugin detection is unchanged: every selected repo is scanned.
    assert [p["repo"] for p in plugins] == ["repo-a", "repo-b"]
