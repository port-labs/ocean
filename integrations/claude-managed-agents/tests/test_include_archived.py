from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from claude_managed_agents.actions.archive_agent_executor import ArchiveAgentExecutor
from claude_managed_agents.integration import (
    AgentResourceConfig,
    AgentSelector,
    ArchivableSelector,
    EnvironmentResourceConfig,
    EnvironmentSelector,
    MemoryStoreResourceConfig,
    MemoryStoreSelector,
    SessionResourceConfig,
    SessionSelector,
    VaultResourceConfig,
    VaultSelector,
)
from claude_managed_agents.webhook_processors.agent_webhook_processor import (
    AgentWebhookProcessor,
)
from claude_managed_agents.webhook_processors.environment_webhook_processor import (
    EnvironmentWebhookProcessor,
)
from claude_managed_agents.webhook_processors.memory_store_webhook_processor import (
    MemoryStoreWebhookProcessor,
)
from claude_managed_agents.webhook_processors.session_webhook_processor import (
    SessionWebhookProcessor,
)
from claude_managed_agents.webhook_processors.vault_webhook_processor import (
    VaultWebhookProcessor,
)
from tests.action_test_helpers import (
    build_executor,
    build_mock_ocean,
    mock_event_context,
    sdk_agent,
)

_ARCHIVED_AT = "2026-01-01T00:00:00Z"


def _event(data: dict[str, Any]) -> WebhookEvent:
    return WebhookEvent(trace_id="trace", payload={"data": data}, headers={})


def _resource_config(config_cls: type, selector: Any) -> MagicMock:
    config = MagicMock(spec=config_cls)
    config.selector = selector
    return config


def _sdk_resource(raw: dict[str, Any]) -> MagicMock:
    resource = MagicMock()
    resource.archived_at = raw.get("archived_at")
    resource.to_dict.return_value = raw
    return resource


_RESOURCE_CASES = [
    pytest.param(
        AgentWebhookProcessor,
        "agent_webhook_processor",
        "get_agent",
        "agent.archived",
        AgentResourceConfig,
        AgentSelector,
        id="agent",
    ),
    pytest.param(
        EnvironmentWebhookProcessor,
        "environment_webhook_processor",
        "get_environment",
        "environment.archived",
        EnvironmentResourceConfig,
        EnvironmentSelector,
        id="environment",
    ),
    pytest.param(
        VaultWebhookProcessor,
        "vault_webhook_processor",
        "get_vault",
        "vault.archived",
        VaultResourceConfig,
        VaultSelector,
        id="vault",
    ),
    pytest.param(
        MemoryStoreWebhookProcessor,
        "memory_store_webhook_processor",
        "get_memory_store",
        "memory_store.archived",
        MemoryStoreResourceConfig,
        MemoryStoreSelector,
        id="memory-store",
    ),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "processor_cls, module, getter, event_type, config_cls, selector_cls",
    _RESOURCE_CASES,
)
async def test_archived_resource_is_deleted_when_include_archived_is_off(
    processor_cls: type,
    module: str,
    getter: str,
    event_type: str,
    config_cls: type,
    selector_cls: type[ArchivableSelector],
) -> None:
    payload = {"data": {"type": event_type, "id": "r1"}}
    processor = processor_cls(_event(payload["data"]))
    client = MagicMock()
    setattr(
        client,
        getter,
        AsyncMock(
            return_value=_sdk_resource({"id": "r1", "archived_at": _ARCHIVED_AT})
        ),
    )
    config = _resource_config(
        config_cls, selector_cls.parse_obj({"query": "true", "includeArchived": False})
    )

    with patch(
        f"claude_managed_agents.webhook_processors.{module}.create_anthropic_client",
        return_value=client,
    ):
        results = await processor.handle_event(payload, config)

    assert results.updated_raw_results == []
    assert results.deleted_raw_results == [{"id": "r1"}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "processor_cls, module, getter, event_type, config_cls, selector_cls",
    _RESOURCE_CASES,
)
@pytest.mark.parametrize("include_archived", [True, None])
async def test_archived_resource_is_upserted_when_include_archived_is_on(
    processor_cls: type,
    module: str,
    getter: str,
    event_type: str,
    config_cls: type,
    selector_cls: type[ArchivableSelector],
    include_archived: bool | None,
) -> None:
    """`None` stands for a webhook without a resource config; there is no
    selector to filter on, so the resource is upserted."""
    raw = {"id": "r1", "archived_at": _ARCHIVED_AT}
    payload = {"data": {"type": event_type, "id": "r1"}}
    processor = processor_cls(_event(payload["data"]))
    client = MagicMock()
    setattr(client, getter, AsyncMock(return_value=_sdk_resource(raw)))
    config = (
        None
        if include_archived is None
        else _resource_config(
            config_cls,
            selector_cls.parse_obj(
                {"query": "true", "includeArchived": include_archived}
            ),
        )
    )

    with patch(
        f"claude_managed_agents.webhook_processors.{module}.create_anthropic_client",
        return_value=client,
    ):
        results = await processor.handle_event(payload, config)

    assert results.updated_raw_results == [raw]
    assert results.deleted_raw_results == []


@pytest.mark.asyncio
async def test_active_resource_is_upserted_when_include_archived_is_off() -> None:
    raw = {"id": "a1", "archived_at": None}
    payload = {"data": {"type": "agent.updated", "id": "a1"}}
    processor = AgentWebhookProcessor(_event(payload["data"]))
    client = MagicMock()
    client.get_agent = AsyncMock(return_value=_sdk_resource(raw))
    config = _resource_config(
        AgentResourceConfig,
        AgentSelector.parse_obj({"query": "true", "includeArchived": False}),
    )

    with patch(
        "claude_managed_agents.webhook_processors.agent_webhook_processor.create_anthropic_client",
        return_value=client,
    ):
        results = await processor.handle_event(payload, config)

    assert results.updated_raw_results == [raw]


def _session_raw(session_id: str = "s1", **overrides: Any) -> dict[str, Any]:
    raw: dict[str, Any] = {
        "id": session_id,
        "archived_at": None,
        "agent": {"id": "a1"},
        "environment_id": "e1",
        "vault_ids": [],
        "resources": [],
    }
    raw.update(overrides)
    return raw


def _session_client(raw: dict[str, Any], *, archived_agent: bool) -> MagicMock:
    client = MagicMock()
    client.get_session = AsyncMock(return_value=_sdk_resource(raw))
    client.get_agent = AsyncMock(
        return_value=_sdk_resource(
            {"id": "a1", "archived_at": _ARCHIVED_AT if archived_agent else None}
        )
    )
    client.get_environment = AsyncMock(
        return_value=_sdk_resource({"id": "e1", "archived_at": None})
    )
    return client


async def _handle_session(
    raw: dict[str, Any], client: MagicMock, config: MagicMock | None
) -> Any:
    payload = {"data": {"type": "session.idled", "id": raw["id"]}}
    processor = SessionWebhookProcessor(_event(payload["data"]))
    with patch(
        "claude_managed_agents.webhook_processors.session_webhook_processor.create_anthropic_client",
        return_value=client,
    ):
        return await processor.handle_event(payload, config)


def _session_config(**selector: Any) -> MagicMock:
    return _resource_config(
        SessionResourceConfig, SessionSelector.parse_obj({"query": "true", **selector})
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [_session_config(), _session_config(includeSessionsOfArchivedResources=False)],
    ids=["default", "explicit"],
)
async def test_session_of_archived_resource_is_deleted_when_selector_is_off(
    config: MagicMock,
) -> None:
    raw = _session_raw()
    client = _session_client(raw, archived_agent=True)

    results = await _handle_session(raw, client, config)

    assert results.updated_raw_results == []
    assert results.deleted_raw_results == [{"id": "s1"}]


@pytest.mark.asyncio
async def test_session_of_active_resources_is_upserted_when_selector_is_off() -> None:
    raw = _session_raw()
    client = _session_client(raw, archived_agent=False)

    results = await _handle_session(
        raw, client, _session_config(includeSessionsOfArchivedResources=False)
    )

    assert results.updated_raw_results == [raw]
    assert results.deleted_raw_results == []


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "config",
    [None, _session_config(includeSessionsOfArchivedResources=True)],
    ids=["no-config", "selector-on"],
)
async def test_session_of_archived_resource_is_upserted_when_selector_is_on(
    config: MagicMock | None,
) -> None:
    raw = _session_raw()
    client = _session_client(raw, archived_agent=True)

    results = await _handle_session(raw, client, config)

    assert results.updated_raw_results == [raw]
    client.get_agent.assert_not_awaited()


@pytest.mark.asyncio
async def test_archived_session_is_deleted_when_include_archived_is_off() -> None:
    raw = _session_raw(archived_at=_ARCHIVED_AT)
    client = _session_client(raw, archived_agent=False)

    results = await _handle_session(raw, client, _session_config(includeArchived=False))

    assert results.updated_raw_results == []
    assert results.deleted_raw_results == [{"id": "s1"}]


def _archive_executor_run() -> MagicMock:
    run = MagicMock()
    run.id = "run_1"
    run.execution_properties = {"agentId": "agent_1"}
    return run


async def _execute_archive(*agent_selectors: AgentSelector) -> MagicMock:
    client_mock = MagicMock()
    client_mock.archive_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(ArchiveAgentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock(
        return_value=SimpleNamespace(
            resources=[
                _resource_config(AgentResourceConfig, selector)
                for selector in agent_selectors
            ]
        )
    )

    with (
        patch("claude_managed_agents.actions.archive_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(_archive_executor_run())

    return mock_ocean


@pytest.mark.asyncio
async def test_archive_agent_executor_unregisters_when_include_archived_is_off() -> (
    None
):
    mock_ocean = await _execute_archive(
        AgentSelector.parse_obj({"query": "true", "includeArchived": False})
    )

    mock_ocean.unregister_raw.assert_awaited_once_with("agent", [{"id": "agent_1"}])
    mock_ocean.register_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_agent_executor_registers_when_any_mapping_includes_archived() -> (
    None
):
    mock_ocean = await _execute_archive(
        AgentSelector.parse_obj({"query": "true", "includeArchived": False}),
        AgentSelector.parse_obj({"query": "true", "includeArchived": True}),
    )

    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.unregister_raw.assert_not_awaited()


@pytest.mark.asyncio
async def test_archive_agent_executor_registers_when_config_cannot_be_read() -> None:
    client_mock = MagicMock()
    client_mock.archive_agent = AsyncMock(return_value=sdk_agent())
    executor = build_executor(ArchiveAgentExecutor, client_mock)

    mock_ocean = build_mock_ocean()
    mock_ocean.port_client.report_run_completed = AsyncMock()
    mock_ocean.integration.port_app_config_handler.get_port_app_config = AsyncMock(
        # The first call is the includeArchived lookup; `register_entity`
        # fetches the config again before upserting.
        side_effect=[RuntimeError("port down"), SimpleNamespace(resources=[])]
    )

    with (
        patch("claude_managed_agents.actions.archive_agent_executor.ocean", mock_ocean),
        patch("claude_managed_agents.actions.abstract_executor.ocean", mock_ocean),
        patch(
            "claude_managed_agents.actions.abstract_executor.event_context",
            mock_event_context,
        ),
    ):
        await executor.execute(_archive_executor_run())

    mock_ocean.register_raw.assert_awaited_once()
    mock_ocean.unregister_raw.assert_not_awaited()
