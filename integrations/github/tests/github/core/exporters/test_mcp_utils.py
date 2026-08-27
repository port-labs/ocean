from github.core.exporters.mcp_exporter.utils import (
    build_mcp_raw_item,
    iter_mcp_servers,
)

REPOSITORY = {"name": "example-plugin", "full_name": "acme/example-plugin"}


class TestMcpUtils:
    def test_iter_mcp_servers_yields_only_dict_values(self) -> None:
        content = {
            "mcpServers": {
                "port": {"url": "https://mcp.port.io/v1"},
                "broken": "not-a-dict",
            }
        }
        assert list(iter_mcp_servers(content)) == [
            ("port", {"url": "https://mcp.port.io/v1"})
        ]

    def test_iter_mcp_servers_handles_missing_or_malformed_keys(self) -> None:
        assert list(iter_mcp_servers({})) == []
        assert list(iter_mcp_servers({"mcpServers": "nope"})) == []
        assert list(iter_mcp_servers("not-a-dict")) == []

    def test_build_mcp_raw_item_derives_http_transport(self) -> None:
        item = build_mcp_raw_item(
            file_path=".mcp.json",
            server_name="port",
            server_config={
                "url": "https://mcp.port.io/v1",
                "headers": {"x-read-only-mode": "0"},
            },
            repository=REPOSITORY,
            branch="main",
            organization="acme",
        )
        mcp = item["mcp"]
        assert mcp["name"] == "port"
        assert mcp["transport"] == "http"
        assert mcp["url"] == "https://mcp.port.io/v1"
        assert mcp["headers"] == {"x-read-only-mode": "0"}
        assert mcp["config"] == {
            "url": "https://mcp.port.io/v1",
            "headers": {"x-read-only-mode": "0"},
        }
        assert item["__repository"] == REPOSITORY
        assert item["__branch"] == "main"
        assert item["__organization"] == "acme"

    def test_build_mcp_raw_item_derives_stdio_transport(self) -> None:
        item = build_mcp_raw_item(
            file_path="mcp.json",
            server_name="filesystem",
            server_config={
                "command": "npx",
                "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
                "env": {"NODE_ENV": "development"},
            },
            repository=REPOSITORY,
            branch="main",
        )
        mcp = item["mcp"]
        assert mcp["transport"] == "stdio"
        assert mcp["command"] == "npx"
        assert mcp["args"] == ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"]
        assert mcp["env"] == {"NODE_ENV": "development"}
        assert item["__organization"] is None

    def test_delete_stub_shares_identity_with_upsert(self) -> None:
        """A delete stub built with empty server_config must carry the same
        identifying fields (name/path) as the original upsert, so Port can
        resolve it to the same entity."""
        upsert = build_mcp_raw_item(
            file_path=".mcp.json",
            server_name="port",
            server_config={"url": "https://mcp.port.io/v1"},
            repository=REPOSITORY,
            branch="main",
        )
        delete_stub = build_mcp_raw_item(
            file_path=".mcp.json",
            server_name="port",
            server_config={},
            repository=REPOSITORY,
            branch="main",
        )
        assert upsert["mcp"]["name"] == delete_stub["mcp"]["name"]
        assert upsert["mcp"]["path"] == delete_stub["mcp"]["path"]
        assert delete_stub["mcp"]["transport"] == "stdio"
        assert delete_stub["mcp"]["config"] == {}
