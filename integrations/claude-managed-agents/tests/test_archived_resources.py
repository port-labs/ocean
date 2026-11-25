from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from port_ocean.utils.ttl_cache import TTLCache

from claude_managed_agents.core import archived_resources
from claude_managed_agents.core.archived_resources import (
    ArchivedResourceChecker,
    SessionReferences,
)
from claude_managed_agents.core.exporters.sessions_exporter import SessionsExporter
from claude_managed_agents.integration import (
    AgentSelector,
    EnvironmentSelector,
    MemoryStoreSelector,
    ObjectKind,
    SessionSelector,
    VaultSelector,
)


@pytest.fixture(autouse=True)
def _fresh_archived_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        archived_resources,
        "_archived_resources_cache",
        TTLCache[bool](ttl_seconds=60, max_items=100),
    )


def _model(data: dict[str, Any]) -> MagicMock:
    model = MagicMock()
    model.to_dict.return_value = data
    return model


def _session(
    session_id: str,
    *,
    agent_id: str = "agent_active",
    environment_id: str = "env_active",
    vault_ids: list[str] | None = None,
    memory_store_ids: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "id": session_id,
        "agent": {"id": agent_id},
        "environment_id": environment_id,
        "vault_ids": vault_ids or [],
        "resources": [
            {"type": "memory_store", "memory_store_id": memory_store_id}
            for memory_store_id in memory_store_ids or []
        ]
        + [{"type": "github_repository", "url": "https://github.com/port/ocean"}],
    }


def _resource(resource_id: str, *, archived: bool) -> dict[str, Any]:
    return {
        "id": resource_id,
        "archived_at": "2026-01-01T00:00:00Z" if archived else None,
    }


def _client_listing(
    *,
    agents: list[dict[str, Any]],
    environments: list[dict[str, Any]] | None = None,
    vaults: list[dict[str, Any]] | None = None,
    memory_stores: list[dict[str, Any]] | None = None,
    sessions: list[list[dict[str, Any]]] | None = None,
) -> MagicMock:
    """Client whose `paginate` yields the records registered for each list call."""
    client = MagicMock()
    pages_by_call: dict[int, list[list[dict[str, Any]]]] = {}

    def register(resource: MagicMock, pages: list[list[dict[str, Any]]]) -> None:
        resource.list.return_value = MagicMock()
        pages_by_call[id(resource.list.return_value)] = pages

    register(client.beta.agents, [agents])
    register(client.beta.environments, [environments or []])
    register(client.beta.vaults, [vaults or []])
    register(client.beta.memory_stores, [memory_stores or []])
    register(client.beta.sessions, sessions or [])

    async def paginate(call: MagicMock) -> AsyncGenerator[list[MagicMock], None]:
        for page in pages_by_call[id(call)]:
            yield [_model(item) for item in page]

    client.paginate = paginate
    return client


def test_selector_defaults() -> None:
    assert AgentSelector(query="true").include_archived is False
    assert EnvironmentSelector(query="true").include_archived is False
    assert VaultSelector(query="true").include_archived is False
    assert MemoryStoreSelector(query="true").include_archived is False

    session_selector = SessionSelector(query="true")
    assert session_selector.include_archived is False
    assert session_selector.include_sessions_of_archived_resources is False


def test_session_selector_reads_alias() -> None:
    selector = SessionSelector.parse_obj(
        {"query": "true", "includeSessionsOfArchivedResources": True}
    )
    assert selector.include_sessions_of_archived_resources is True


def test_session_referenced_ids() -> None:
    session = _session(
        "s1",
        agent_id="a1",
        environment_id="e1",
        vault_ids=["v1", "v2"],
        memory_store_ids=["m1"],
    )
    assert SessionReferences.model_validate(session).referenced_ids() == {
        ObjectKind.AGENT: {"a1"},
        ObjectKind.ENVIRONMENT: {"e1"},
        ObjectKind.VAULT: {"v1", "v2"},
        ObjectKind.MEMORY_STORE: {"m1"},
    }


def test_session_referenced_ids_handle_missing_fields() -> None:
    assert SessionReferences.model_validate({"id": "s1"}).referenced_ids() == {
        ObjectKind.AGENT: set(),
        ObjectKind.ENVIRONMENT: set(),
        ObjectKind.VAULT: set(),
        ObjectKind.MEMORY_STORE: set(),
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "session",
    [
        _session("s1", agent_id="agent_archived"),
        _session("s2", environment_id="env_archived"),
        _session("s3", vault_ids=["vault_active", "vault_archived"]),
        _session("s4", memory_store_ids=["memory_archived"]),
    ],
)
async def test_loaded_checker_flags_sessions_referencing_archived_resources(
    session: dict[str, Any],
) -> None:
    client = _client_listing(
        agents=[
            _resource("agent_active", archived=False),
            _resource("agent_archived", archived=True),
        ],
        environments=[_resource("env_archived", archived=True)],
        vaults=[_resource("vault_archived", archived=True)],
        memory_stores=[_resource("memory_archived", archived=True)],
    )
    checker = ArchivedResourceChecker(client)
    await checker.load_archived_ids()

    assert await checker.session_references_archived_resource(session) is True


@pytest.mark.asyncio
async def test_loaded_checker_keeps_sessions_of_active_resources() -> None:
    client = _client_listing(
        agents=[_resource("agent_active", archived=False)],
        environments=[_resource("env_active", archived=False)],
    )
    checker = ArchivedResourceChecker(client)
    await checker.load_archived_ids()

    session = _session("s1", vault_ids=["vault_unknown"])
    assert await checker.session_references_archived_resource(session) is False


@pytest.mark.asyncio
async def test_loaded_checker_lists_every_kind_with_archived_included() -> None:
    client = _client_listing(agents=[])
    await ArchivedResourceChecker(client).load_archived_ids()

    for resource in (
        client.beta.agents,
        client.beta.environments,
        client.beta.vaults,
        client.beta.memory_stores,
    ):
        resource.list.assert_called_once_with(include_archived=True)


async def _archived_retrieve(_resource_id: str) -> MagicMock:
    resource = MagicMock()
    resource.archived_at = "2026-01-01T00:00:00Z"
    return resource


def _lookup_client(*, archived: set[str]) -> MagicMock:
    client = MagicMock()

    async def retrieve(resource_id: str) -> MagicMock:
        resource = MagicMock()
        resource.archived_at = (
            "2026-01-01T00:00:00Z" if resource_id in archived else None
        )
        return resource

    client.get_agent = AsyncMock(side_effect=retrieve)
    client.get_environment = AsyncMock(side_effect=retrieve)
    client.get_vault = AsyncMock(side_effect=retrieve)
    client.get_memory_store = AsyncMock(side_effect=retrieve)
    return client


@pytest.mark.asyncio
async def test_unloaded_checker_looks_up_each_referenced_resource() -> None:
    client = _lookup_client(archived={"memory_archived"})
    checker = ArchivedResourceChecker(client)

    session = _session(
        "s1", vault_ids=["vault_1"], memory_store_ids=["memory_archived"]
    )
    assert await checker.session_references_archived_resource(session) is True

    client.get_agent.assert_awaited_once_with("agent_active")
    client.get_environment.assert_awaited_once_with("env_active")
    client.get_vault.assert_awaited_once_with("vault_1")
    client.get_memory_store.assert_awaited_once_with("memory_archived")


@pytest.mark.asyncio
async def test_unloaded_checker_always_rechecks_active_resources() -> None:
    """An active resource can be archived while its sessions keep running, so
    an "active" answer must never be cached."""
    client = _lookup_client(archived=set())
    checker = ArchivedResourceChecker(client)
    session = _session("s1")

    assert await checker.session_references_archived_resource(session) is False
    client.get_agent.side_effect = _archived_retrieve
    assert await checker.session_references_archived_resource(session) is True

    assert client.get_agent.await_count == 2


@pytest.mark.asyncio
async def test_unloaded_checker_caches_archived_resources() -> None:
    client = _lookup_client(archived={"agent_archived"})
    checker = ArchivedResourceChecker(client)
    session = _session("s1", agent_id="agent_archived")

    assert await checker.session_references_archived_resource(session) is True
    assert await checker.session_references_archived_resource(session) is True

    client.get_agent.assert_awaited_once_with("agent_archived")


@pytest.mark.asyncio
async def test_unloaded_checker_keeps_session_when_lookup_fails() -> None:
    client = _lookup_client(archived=set())
    client.get_agent = AsyncMock(side_effect=RuntimeError("not found"))

    checker = ArchivedResourceChecker(client)

    assert await checker.session_references_archived_resource(_session("s1")) is False


@pytest.mark.asyncio
async def test_sessions_exporter_skips_sessions_of_archived_resources() -> None:
    client = _client_listing(
        agents=[
            _resource("agent_active", archived=False),
            _resource("agent_archived", archived=True),
        ],
        sessions=[
            [_session("s1"), _session("s2", agent_id="agent_archived")],
            [_session("s3", agent_id="agent_archived")],
            [_session("s4")],
        ],
    )

    exporter = SessionsExporter(client)
    batches = [
        batch
        async for batch in exporter.get_paginated_resources(
            include_sessions_of_archived_resources=False
        )
    ]

    assert [[session["id"] for session in batch] for batch in batches] == [
        ["s1"],
        [],
        ["s4"],
    ]


@pytest.mark.asyncio
async def test_sessions_exporter_keeps_all_sessions_by_default() -> None:
    client = _client_listing(
        agents=[_resource("agent_archived", archived=True)],
        sessions=[[_session("s1", agent_id="agent_archived"), _session("s2")]],
    )

    exporter = SessionsExporter(client)
    batches = [batch async for batch in exporter.get_paginated_resources()]

    assert [[session["id"] for session in batch] for batch in batches] == [["s1", "s2"]]
    client.beta.agents.list.assert_not_called()
