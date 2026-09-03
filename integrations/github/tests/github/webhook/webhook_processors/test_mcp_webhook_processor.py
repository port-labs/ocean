import json
from typing import Any, Dict, Optional
import pytest
from unittest.mock import AsyncMock, patch

from port_ocean.core.handlers.webhook.webhook_event import (
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)
from port_ocean.core.handlers.port_app_config.models import (
    PortResourceConfig,
    EntityMapping,
    MappingsConfig,
)
from integration import (
    GithubMcpPattern,
    GithubMcpResourceConfig,
    GithubMcpSelector,
)
from github.webhook.webhook_processors.mcp_webhook_processor import (
    McpWebhookProcessor,
)
from github.helpers.utils import ObjectKind


@pytest.fixture
def resource_config() -> GithubMcpResourceConfig:
    return GithubMcpResourceConfig(
        kind=ObjectKind.MCP,
        selector=GithubMcpSelector(
            query="true",
            paths=[GithubMcpPattern(path=".mcp.json")],
        ),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".mcp.path",
                    title=".mcp.name",
                    blueprint='"pluginMcpServer"',
                    properties={},
                )
            )
        ),
    )


@pytest.fixture
def mcp_webhook_processor(mock_webhook_event: WebhookEvent) -> McpWebhookProcessor:
    return McpWebhookProcessor(event=mock_webhook_event)


@pytest.fixture
def payload() -> EventPayload:
    return {
        "ref": "refs/heads/main",
        "before": "abc123",
        "after": "def456",
        "commits": [],
        "repository": {"name": "test-repo", "default_branch": "main"},
        "organization": {"login": "test-org"},
    }


def _process_file_side_effect(**kwargs: Any) -> Dict[str, Any]:
    """Stand-in for RestFileExporter.file_processor.process_file: mirrors the
    real JSON-parsing behavior for `.json`-suffixed content."""
    content = kwargs["content"]
    parsed = json.loads(content) if isinstance(content, str) else content
    return {"content": parsed}


def _by_ref(responses: Dict[Optional[str], Any]) -> Any:
    """get_resource side_effect keyed by the `branch` (ref) it was called
    with, so tests don't depend on call ordering inside handle_event."""

    def _side_effect(options: Dict[str, Any]) -> Any:
        return responses.get(options["branch"])

    return _side_effect


def _mcp_content(servers: Dict[str, Any]) -> str:
    return json.dumps({"mcpServers": servers})


@pytest.mark.asyncio
class TestMcpWebhookProcessor:
    async def test_get_matching_kinds(
        self, mcp_webhook_processor: McpWebhookProcessor
    ) -> None:
        kinds = await mcp_webhook_processor.get_matching_kinds(
            WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
        )
        assert kinds == [ObjectKind.MCP]

    async def test_handle_event_new_server_added_to_existing_file(
        self,
        mcp_webhook_processor: McpWebhookProcessor,
        resource_config: GithubMcpResourceConfig,
        payload: EventPayload,
    ) -> None:
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": ".mcp.json", "status": "modified"}]
        }
        mock_exporter.get_resource.side_effect = _by_ref(
            {
                "main": {
                    "content": _mcp_content(
                        {
                            "port": {"url": "https://mcp.port.io/v1"},
                            "filesystem": {"command": "npx"},
                        }
                    ),
                    "sha": "new-sha",
                },
                "abc123": {
                    "content": _mcp_content(
                        {"port": {"url": "https://mcp.port.io/v1"}}
                    ),
                    "sha": "old-sha",
                },
            }
        )
        mock_exporter.file_processor.process_file = AsyncMock(
            side_effect=_process_file_side_effect
        )

        with (
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await mcp_webhook_processor.handle_event(payload, resource_config)

        assert isinstance(result, WebhookEventRawResults)
        assert result.deleted_raw_results == []
        names = {item["mcp"]["name"] for item in result.updated_raw_results}
        assert names == {"port", "filesystem"}
        assert all(
            item["mcp"]["blob_sha"] == "new-sha" for item in result.updated_raw_results
        )

    async def test_handle_event_whole_file_removed_deletes_all_previous_servers(
        self,
        mcp_webhook_processor: McpWebhookProcessor,
        resource_config: GithubMcpResourceConfig,
        payload: EventPayload,
    ) -> None:
        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": ".mcp.json", "status": "removed"}]
        }
        mock_exporter.get_resource.return_value = {
            "content": _mcp_content(
                {
                    "port": {"url": "https://mcp.port.io/v1"},
                    "filesystem": {"command": "npx"},
                }
            ),
            "sha": "old-sha",
        }
        mock_exporter.file_processor.process_file = AsyncMock(
            side_effect=_process_file_side_effect
        )

        with (
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await mcp_webhook_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        deleted_names = {item["mcp"]["name"] for item in result.deleted_raw_results}
        assert deleted_names == {"port", "filesystem"}
        assert all(
            item["mcp"]["blob_sha"] == "old-sha" for item in result.deleted_raw_results
        )

    async def test_handle_event_server_removed_from_file_still_present(
        self,
        mcp_webhook_processor: McpWebhookProcessor,
        resource_config: GithubMcpResourceConfig,
        payload: EventPayload,
    ) -> None:
        """The full-diff behavior: a single mcpServers key disappearing from a
        file that still exists must be reflected as a delete immediately,
        without waiting for a full resync."""

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": ".mcp.json", "status": "modified"}]
        }
        mock_exporter.get_resource.side_effect = _by_ref(
            {
                "main": {
                    "content": _mcp_content(
                        {"port": {"url": "https://mcp.port.io/v1"}}
                    ),
                    "sha": "new-sha",
                },
                "abc123": {
                    "content": _mcp_content(
                        {
                            "port": {"url": "https://mcp.port.io/v1"},
                            "filesystem": {"command": "npx"},
                        }
                    ),
                    "sha": "old-sha",
                },
            }
        )
        mock_exporter.file_processor.process_file = AsyncMock(
            side_effect=_process_file_side_effect
        )

        with (
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await mcp_webhook_processor.handle_event(payload, resource_config)

        assert {item["mcp"]["name"] for item in result.updated_raw_results} == {"port"}
        assert {item["mcp"]["name"] for item in result.deleted_raw_results} == {
            "filesystem"
        }
        assert result.deleted_raw_results[0]["mcp"]["blob_sha"] == "old-sha"

    async def test_handle_event_current_fetch_failure_skips_file_without_deleting(
        self,
        mcp_webhook_processor: McpWebhookProcessor,
        resource_config: GithubMcpResourceConfig,
        payload: EventPayload,
    ) -> None:
        """Regression test: GitHub's client silently swallows 401/403/404 into
        an empty response, indistinguishable from "file not found". If the
        *current*-branch fetch for a file the diff says still exists comes
        back empty/failed, we must not treat that as "zero servers" and wipe
        every previously known entity for that file."""

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": ".mcp.json", "status": "modified"}]
        }
        # Simulates a swallowed 403/404: get_resource returns falsy.
        mock_exporter.get_resource.side_effect = _by_ref({"main": None})
        mock_exporter.file_processor.process_file = AsyncMock(
            side_effect=_process_file_side_effect
        )

        with (
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await mcp_webhook_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
        # Must bail out after the failed current-branch fetch without ever
        # attempting to fetch the old content to compute a diff-based delete.
        mock_exporter.get_resource.assert_called_once()

    async def test_handle_event_oversized_current_content_skips_without_deleting(
        self,
        mcp_webhook_processor: McpWebhookProcessor,
        resource_config: GithubMcpResourceConfig,
        payload: EventPayload,
    ) -> None:
        """Same regression as above, but for the file-too-large/non-file case,
        where get_resource returns a truthy response with `content: None`."""

        mock_exporter = AsyncMock()
        mock_exporter.fetch_commit_diff.return_value = {
            "files": [{"filename": ".mcp.json", "status": "modified"}]
        }
        mock_exporter.get_resource.side_effect = _by_ref(
            {"main": {"content": None, "sha": "new-sha"}}
        )
        mock_exporter.file_processor.process_file = AsyncMock(
            side_effect=_process_file_side_effect
        )

        with (
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.create_github_client_for_org",
                return_value=AsyncMock(),
            ),
            patch(
                "github.webhook.webhook_processors.mcp_webhook_processor.RestFileExporter",
                return_value=mock_exporter,
            ),
        ):
            result = await mcp_webhook_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []

    async def test_handle_event_no_matching_patterns_returns_empty(
        self,
        mcp_webhook_processor: McpWebhookProcessor,
        resource_config: GithubMcpResourceConfig,
        payload: EventPayload,
    ) -> None:
        resource_config.selector.paths = [
            GithubMcpPattern(path=".mcp.json", organization="other-org")
        ]

        result = await mcp_webhook_processor.handle_event(payload, resource_config)

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []
