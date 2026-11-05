from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import yaml  # type: ignore[import-untyped]

from core.exporters.knowledge_notes_exporter import KnowledgeNotesExporter
from core.exporters.playbooks_exporter import PlaybooksExporter
from core.exporters.secrets_exporter import SecretsExporter
from core.exporters.sessions_exporter import SessionsExporter, build_sessions_query
from integration import DevinPortAppConfig, SessionResourceConfig

RESOURCES_DIR = Path(__file__).parent.parent / ".port" / "resources"


def _paginating_client(*pages: list[dict[str, Any]]) -> MagicMock:
    client = MagicMock()
    calls: list[tuple[str, dict[str, Any] | None]] = []

    async def paginate(path: str, params: dict[str, Any] | None = None) -> Any:
        calls.append((path, params))
        for page in pages:
            yield page

    client.paginate = paginate
    client.calls = calls
    return client


def test_default_sessions_query() -> None:
    assert build_sessions_query(
        include_archived=False,
        created_after_days=30,
        origins=None,
        only_managed_by_port=False,
        now=100 * 86400,
    ) == {"is_archived": False, "created_after": 70 * 86400}


def test_sessions_query_with_every_selector() -> None:
    assert build_sessions_query(
        include_archived=True,
        created_after_days=None,
        origins=["api", "slack"],
        only_managed_by_port=True,
    ) == {"origins": ["api", "slack"], "tags": ["port:managed"]}


async def test_sessions_exporter_passes_query_to_client() -> None:
    client = _paginating_client([{"session_id": "devin-1"}])
    exporter = SessionsExporter(client)

    pages = [
        page
        async for page in exporter.get_paginated_resources(
            include_archived=True, created_after_days=None, only_managed_by_port=True
        )
    ]

    assert pages == [[{"session_id": "devin-1"}]]
    assert client.calls == [("/sessions", {"tags": ["port:managed"]})]


async def test_playbooks_exporter_include_enterprise() -> None:
    client = _paginating_client([{"playbook_id": "p1"}])

    pages = [
        page
        async for page in PlaybooksExporter(client).get_paginated_resources(
            include_enterprise=True
        )
    ]

    assert pages == [[{"playbook_id": "p1"}]]
    assert client.calls == [("/playbooks", {"include_enterprise": True})]


async def test_knowledge_notes_exporter() -> None:
    client = _paginating_client([{"note_id": "n1"}])

    pages = [
        page async for page in KnowledgeNotesExporter(client).get_paginated_resources()
    ]

    assert pages == [[{"note_id": "n1"}]]
    assert client.calls == [("/knowledge/notes", None)]


async def test_secrets_exporter_get_resource_scans_the_list() -> None:
    client = _paginating_client([{"secret_id": "s1"}, {"secret_id": "s2"}])

    assert await SecretsExporter(client).get_resource("s2") == {"secret_id": "s2"}
    assert await SecretsExporter(client).get_resource("missing") == {}


async def test_sessions_exporter_get_resource() -> None:
    client = MagicMock()
    client.send_api_request = AsyncMock(return_value={"session_id": "devin-1"})

    assert await SessionsExporter(client).get_resource("devin-1") == {
        "session_id": "devin-1"
    }
    client.send_api_request.assert_awaited_once_with("GET", "/sessions/devin-1")


def test_default_port_app_config_parses() -> None:
    raw = yaml.safe_load((RESOURCES_DIR / "port-app-config.yml").read_text())

    config = DevinPortAppConfig.parse_obj(raw)

    kinds = [resource.kind for resource in config.resources]
    assert kinds == ["playbook", "knowledge-note", "secret", "session"]
    session = config.resources[-1]
    assert isinstance(session, SessionResourceConfig)
    assert session.selector.created_after_days == 30
    assert session.selector.only_managed_by_port is False
