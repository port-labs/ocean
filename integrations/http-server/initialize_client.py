"""
HTTP Server Client Factory

Factory function to create HTTP server client instances from Ocean configuration.
"""

from http_server.client import HttpServerClient
from port_ocean.context.ocean import ocean


def init_client() -> HttpServerClient:
    """Initialize HTTP server client from Ocean configuration"""
    config = ocean.integration_config
    
    return HttpServerClient(
        base_url=config["base_url"],
        auth_type=config.get("auth_type", "none"),
        auth_config=config,
        pagination_config=config,
        timeout=config.get("timeout", 30),
        verify_ssl=config.get("verify_ssl", True),
        max_concurrent_requests=config.get("max_concurrent_requests", 10),
    )


