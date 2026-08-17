from typing import Any, AsyncGenerator, Dict, List

import pytest
from unittest.mock import MagicMock, AsyncMock

from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from azure_devops.webhooks.webhook_processors.wiki_webhook_processor import (
    WikiWebhookProcessor,
)
from azure_devops.webhooks.events import PushEvents
from tests.conftest import MOCK_RESOURCE_CONTAINERS_ACCOUNT, mock_client_manager

MOCK_WIKI_PUSH_PAYLOAD = {
    "eventType": PushEvents.PUSH,
    "publisherId": "tfs",
    "resource": {
        "repository": {
            "id": "wiki-guid-1",
            "name": "MyProject.wiki",
            "project": {"id": "proj-1", "name": "MyProject"},
        },
        "refUpdates": [
            {"name": "refs/heads/wikiMaster", "newObjectId": "abc123"},
        ],
    },
    "resourceContainers": MOCK_RESOURCE_CONTAINERS_ACCOUNT,
}

MOCK_CODE_PUSH_PAYLOAD = {
    "eventType": PushEvents.PUSH,
    "publisherId": "tfs",
    "resource": {
        "repository": {
            "id": "repo-guid-1",
            "name": "MyProject",
            "project": {"id": "proj-1", "name": "MyProject"},
        },
        "refUpdates": [
            {"name": "refs/heads/main", "newObjectId": "def456"},
        ],
    },
    "resourceContainers": MOCK_RESOURCE_CONTAINERS_ACCOUNT,
}


@pytest.fixture
def wiki_resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="wiki",
        selector=Selector(query="true"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier='.__wiki.id + "/" + (.id | tostring)',
                    title='.path | split("/") | last',
                    blueprint='"azureDevopsWiki"',
                    properties={"path": ".path"},
                    relations={},
                )
            )
        ),
    )


def _make_processor(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> tuple[WikiWebhookProcessor, MagicMock]:
    mock_client = MagicMock()
    mock_client._organization_base_url = "https://dev.azure.com/test"
    mock_client.excluded_tags = None
    mock_client.get_wiki = AsyncMock()
    mock_client_manager(monkeypatch, mock_client)
    return WikiWebhookProcessor(event), mock_client


# ── should_process_event ────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_should_process_wiki_push(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor, _ = _make_processor(event, monkeypatch)
    wiki_event = WebhookEvent(trace_id="t1", payload=MOCK_WIKI_PUSH_PAYLOAD, headers={})
    assert await processor.should_process_event(wiki_event) is True


@pytest.mark.asyncio
async def test_should_not_process_regular_push(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor, _ = _make_processor(event, monkeypatch)
    code_event = WebhookEvent(trace_id="t1", payload=MOCK_CODE_PUSH_PAYLOAD, headers={})
    assert await processor.should_process_event(code_event) is False


@pytest.mark.asyncio
async def test_should_not_process_non_push_event(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor, _ = _make_processor(event, monkeypatch)
    non_push = WebhookEvent(
        trace_id="t1",
        payload={
            "eventType": "git.pullrequest.created",
            "publisherId": "tfs",
            "resource": {
                "repository": {
                    "id": "wiki-guid-1",
                    "name": "MyProject.wiki",
                    "project": {"id": "proj-1"},
                },
            },
        },
        headers={},
    )
    assert await processor.should_process_event(non_push) is False


# ── validate_payload ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_validate_payload_wiki_push(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor, _ = _make_processor(event, monkeypatch)
    assert await processor.validate_payload(MOCK_WIKI_PUSH_PAYLOAD) is True


@pytest.mark.asyncio
async def test_validate_payload_rejects_regular_repo(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor, _ = _make_processor(event, monkeypatch)
    assert await processor.validate_payload(MOCK_CODE_PUSH_PAYLOAD) is False


@pytest.mark.asyncio
async def test_validate_payload_rejects_missing_project_id(
    event: WebhookEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    processor, _ = _make_processor(event, monkeypatch)
    payload = {
        "eventType": PushEvents.PUSH,
        "publisherId": "tfs",
        "resource": {
            "repository": {
                "id": "wiki-guid-1",
                "name": "MyProject.wiki",
                "project": {},
            },
        },
    }
    assert await processor.validate_payload(payload) is False


# ── handle_event ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_handle_event_fetches_wiki_pages(
    event: WebhookEvent,
    monkeypatch: pytest.MonkeyPatch,
    mock_event_context: None,
    wiki_resource_config: ResourceConfig,
) -> None:
    processor, mock_client = _make_processor(event, monkeypatch)

    mock_client.get_wiki = AsyncMock(
        return_value={
            "id": "wiki-guid-1",
            "name": "MyProject.wiki",
            "type": "projectWiki",
        }
    )

    pages = [
        {"id": 1, "path": "/Home", "order": 0},
        {"id": 2, "path": "/Getting-Started", "order": 1},
    ]

    async def mock_pages_batch(
        project_id: str, wiki_id: str, wiki_name: str, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield pages

    mock_client.get_wiki_pages_batch = mock_pages_batch

    result = await processor.handle_event(MOCK_WIKI_PUSH_PAYLOAD, wiki_resource_config)

    assert len(result.updated_raw_results) == 2
    assert result.deleted_raw_results == []

    page = result.updated_raw_results[0]
    assert page["path"] == "/Home"
    assert page["__wiki"]["name"] == "MyProject.wiki"
    assert page["__project"]["id"] == "proj-1"

    mock_client.get_wiki.assert_called_once_with("proj-1", "wiki-guid-1")


@pytest.mark.asyncio
async def test_handle_event_wiki_not_found(
    event: WebhookEvent,
    monkeypatch: pytest.MonkeyPatch,
    mock_event_context: None,
    wiki_resource_config: ResourceConfig,
) -> None:
    processor, mock_client = _make_processor(event, monkeypatch)
    mock_client.get_wiki = AsyncMock(return_value=None)

    result = await processor.handle_event(MOCK_WIKI_PUSH_PAYLOAD, wiki_resource_config)

    assert result.updated_raw_results == []
    assert result.deleted_raw_results == []
