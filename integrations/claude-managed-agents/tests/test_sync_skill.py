from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, ANY, MagicMock, patch

import pytest

from actions.sync_skill_executor import SyncSkillExecutor


@asynccontextmanager
async def _event_context(*args: Any, **kwargs: Any) -> AsyncIterator[None]:
    yield


def _skill_content(
    name: str = "port-skill-1",
    title: str = "Port Skill",
    instructions: str = "# Skill",
    resources: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    content: dict[str, Any] = {
        "name": name,
        "title": title,
        "instructions": instructions,
    }
    if resources is not None:
        content["resources"] = resources
    return content


def _run(
    port_skill_id: str = "port-skill-1",
    mode: str = "create",
    claude_skill_id: str | None = None,
) -> MagicMock:
    run = MagicMock()
    run.id = "run-1"
    props: dict[str, Any] = {"portSkillId": port_skill_id, "mode": mode}
    if claude_skill_id is not None:
        props["claudeSkillId"] = claude_skill_id
    run.execution_properties = props
    return run


def _mock_ocean() -> MagicMock:
    mock = MagicMock()
    mock.register_raw = AsyncMock()
    mock.integration.port_app_config_handler.get_port_app_config = AsyncMock()
    mock.port_client.report_run_completed = AsyncMock()
    mock.port_client.upsert_entity = AsyncMock()
    return mock


@pytest.mark.asyncio
async def test_sync_skill_create_mode_creates_skill_and_registers_entity() -> None:
    client = MagicMock()
    client.create_skill = AsyncMock(
        return_value={
            "id": "skill_new",
            "display_title": "Port Skill",
            "source": "custom",
            "latest_version": "skillver_new",
        }
    )
    client.create_skill_version = AsyncMock()
    client.get_skill = AsyncMock()

    mock_ocean = _mock_ocean()

    with (
        patch("actions.abstract_executor.create_anthropic_client", return_value=client),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _event_context),
        patch("actions.sync_skill_executor.ocean", mock_ocean),
        patch(
            "actions.sync_skill_executor.fetch_skill_content",
            AsyncMock(return_value=_skill_content()),
        ),
        patch(
            "actions.sync_skill_executor.upsert_claude_skill_entity",
            AsyncMock(),
        ) as upsert_entity,
    ):
        executor = SyncSkillExecutor()
        await executor.execute(_run(mode="create"))

    client.create_skill.assert_awaited_once()
    client.create_skill_version.assert_not_awaited()
    mock_ocean.register_raw.assert_awaited_once()
    upsert_entity.assert_awaited_once_with("skill_new", "port-skill-1")
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True


@pytest.mark.asyncio
async def test_sync_skill_new_version_mode_adds_version_to_existing_skill() -> None:
    client = MagicMock()
    client.create_skill = AsyncMock()
    client.create_skill_version = AsyncMock(return_value={"id": "skillver_new"})
    client.get_skill = AsyncMock(
        return_value={
            "id": "skill_existing",
            "display_title": "Port Skill",
            "source": "custom",
            "latest_version": "skillver_new",
        }
    )

    mock_ocean = _mock_ocean()

    with (
        patch("actions.abstract_executor.create_anthropic_client", return_value=client),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _event_context),
        patch("actions.sync_skill_executor.ocean", mock_ocean),
        patch(
            "actions.sync_skill_executor.fetch_skill_content",
            AsyncMock(return_value=_skill_content()),
        ),
        patch(
            "actions.sync_skill_executor.upsert_claude_skill_entity",
            AsyncMock(),
        ) as upsert_entity,
    ):
        executor = SyncSkillExecutor()
        await executor.execute(
            _run(mode="new_version", claude_skill_id="skill_existing")
        )

    client.create_skill.assert_not_awaited()
    client.create_skill_version.assert_awaited_once_with("skill_existing", ANY)
    client.get_skill.assert_awaited_once_with("skill_existing")
    upsert_entity.assert_awaited_once_with("skill_existing", "port-skill-1")
    mock_ocean.port_client.report_run_completed.assert_awaited_once()
    assert mock_ocean.port_client.report_run_completed.call_args.args[1] is True


@pytest.mark.asyncio
async def test_sync_skill_requires_claude_skill_id_for_new_version_mode() -> None:
    with patch(
        "actions.abstract_executor.create_anthropic_client", return_value=MagicMock()
    ):
        executor = SyncSkillExecutor()

    with pytest.raises(ValueError, match="claudeSkillId"):
        await executor.execute(_run(mode="new_version", claude_skill_id=None))


@pytest.mark.asyncio
async def test_sync_skill_rejects_invalid_mode() -> None:
    with patch(
        "actions.abstract_executor.create_anthropic_client", return_value=MagicMock()
    ):
        executor = SyncSkillExecutor()

    run = MagicMock()
    run.execution_properties = {"portSkillId": "skill-1", "mode": "bad_mode"}
    with pytest.raises(ValueError, match="mode must be"):
        await executor.execute(run)


@pytest.mark.asyncio
async def test_sync_skill_raises_when_no_instructions() -> None:
    with patch(
        "actions.abstract_executor.create_anthropic_client", return_value=MagicMock()
    ):
        executor = SyncSkillExecutor()

    with (
        patch(
            "actions.sync_skill_executor.fetch_skill_content",
            AsyncMock(return_value={"name": "skill-1", "title": "Skill"}),
        ),
    ):
        with pytest.raises(ValueError, match="no instructions"):
            await executor.execute(_run(mode="create"))


@pytest.mark.asyncio
async def test_sync_skill_packages_resources_from_content_api() -> None:
    client = MagicMock()
    client.create_skill = AsyncMock(
        return_value={
            "id": "skill_new",
            "display_title": "Port Skill",
            "source": "custom",
            "latest_version": "skillver_new",
        }
    )
    mock_ocean = _mock_ocean()

    captured_files: list[Any] = []

    async def _capture_create_skill(files: Any, **kwargs: Any) -> dict[str, Any]:
        captured_files.extend(files)
        return {
            "id": "skill_new",
            "display_title": "Port Skill",
            "source": "custom",
            "latest_version": "skillver_new",
        }

    client.create_skill = _capture_create_skill

    with (
        patch("actions.abstract_executor.create_anthropic_client", return_value=client),
        patch("actions.abstract_executor.ocean", mock_ocean),
        patch("actions.abstract_executor.event_context", _event_context),
        patch("actions.sync_skill_executor.ocean", mock_ocean),
        patch(
            "actions.sync_skill_executor.fetch_skill_content",
            AsyncMock(
                return_value=_skill_content(
                    instructions="# Skill",
                    resources=[{"path": "helpers/run.py", "content": "x = 1"}],
                )
            ),
        ),
        patch("actions.sync_skill_executor.upsert_claude_skill_entity", AsyncMock()),
    ):
        executor = SyncSkillExecutor()
        await executor.execute(_run(mode="create"))

    file_paths = [path for path, _ in captured_files]
    assert "port-skill-1/SKILL.md" in file_paths
    assert "port-skill-1/helpers/run.py" in file_paths
