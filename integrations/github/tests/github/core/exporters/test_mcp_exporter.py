from typing import Any, AsyncGenerator, Dict, List
from unittest.mock import patch

from github.clients.http.rest_client import GithubRestClient
from github.core.exporters.file_exporter.core import RestFileExporter
from github.core.exporters.mcp_exporter.core import McpExporter
from github.core.options import FileSearchOptions, ListFileSearchOptions

TEST_REPOSITORY = {"name": "repo1", "full_name": "test-org/repo1"}


def _mcp_search_options(*paths: str) -> List[ListFileSearchOptions]:
    return [
        ListFileSearchOptions(
            organization="test-org",
            repo_name="repo1",
            files=[
                FileSearchOptions(
                    organization="test-org", path=path, skip_parsing=False
                )
                for path in paths
            ],
        )
    ]


def _file_object(
    path: str, content: Any, metadata: Dict[str, Any] | None = None
) -> Dict[str, Any]:
    return {
        "organization": "test-org",
        "content": content,
        "repository": TEST_REPOSITORY,
        "branch": "main",
        "path": path,
        "name": path.rsplit("/", 1)[-1],
        "metadata": metadata if metadata is not None else {},
    }


class TestMcpExporter:
    async def test_maps_each_server_to_a_separate_raw_item(
        self, rest_client: GithubRestClient
    ) -> None:
        content = {
            "mcpServers": {
                "port": {
                    "url": "https://mcp.port.io/v1",
                    "headers": {"x-read-only-mode": "0"},
                },
                "filesystem": {
                    "command": "npx",
                    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                },
            }
        }

        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object(".mcp.json", content)]

        exporter = McpExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _mcp_search_options(".mcp.json")
                )
            ]

        assert len(batches) == 1
        servers = {item["mcp"]["name"]: item["mcp"] for item in batches[0]}
        assert set(servers) == {"port", "filesystem"}

        assert servers["port"]["transport"] == "http"
        assert servers["port"]["url"] == "https://mcp.port.io/v1"
        assert servers["port"]["headers"] == {"x-read-only-mode": "0"}

        assert servers["filesystem"]["transport"] == "stdio"
        assert servers["filesystem"]["command"] == "npx"
        assert servers["filesystem"]["args"] == [
            "-y",
            "@modelcontextprotocol/server-filesystem",
            "/tmp",
        ]

        assert batches[0][0]["__organization"] == "test-org"

    async def test_skips_files_without_object_content(
        self, rest_client: GithubRestClient
    ) -> None:
        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object("mcp.json", "not-json-object")]

        exporter = McpExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _mcp_search_options("mcp.json")
                )
            ]

        assert batches == []

    async def test_skips_files_without_mcp_servers_key(
        self, rest_client: GithubRestClient
    ) -> None:
        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [_file_object("mcp.json", {"unrelated": True})]

        exporter = McpExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _mcp_search_options("mcp.json")
                )
            ]

        assert batches == []

    async def test_maps_metadata_sha_to_blob_sha(
        self, rest_client: GithubRestClient
    ) -> None:
        content = {"mcpServers": {"port": {"url": "https://mcp.port.io/v1"}}}

        async def fake_files(
            _self: RestFileExporter, _options: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [
                _file_object(
                    ".mcp.json",
                    content,
                    metadata={"sha": "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"},
                )
            ]

        exporter = McpExporter(rest_client)
        with patch.object(RestFileExporter, "get_paginated_resources", fake_files):
            batches = [
                batch
                async for batch in exporter.get_paginated_resources(
                    _mcp_search_options(".mcp.json")
                )
            ]

        assert (
            batches[0][0]["mcp"]["blob_sha"]
            == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"
        )
