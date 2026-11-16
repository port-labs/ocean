from typing import Any

from port_ocean.context.ocean import ocean

from langfuse.clients.http.langfuse_client import LangfuseClient

_client: LangfuseClient | None = None


def create_langfuse_client() -> LangfuseClient:
    global _client
    if _client is not None:
        return _client

    config: dict[str, Any] = ocean.integration_config
    _client = LangfuseClient(
        host=config["langfuse_host"],
        public_key=config["langfuse_public_key"],
        secret_key=config["langfuse_secret_key"],
    )
    return _client
