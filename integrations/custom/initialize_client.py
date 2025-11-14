"""
Ocean Custom Client Factory

Factory function to create HTTP client instances from Ocean configuration.
"""

import os
import re
from typing import Dict, Any, Optional

from pydantic import parse_raw_as

from http_server.client import HttpServerClient
from port_ocean.context.ocean import ocean


def _resolve_env_vars(value: str) -> str:
    """Resolve environment variable references in string (e.g., ${VAR_NAME})"""
    def replace_env(match):
        var_name = match.group(1)
        return os.getenv(var_name, match.group(0))  # Return original if not found
    
    return re.sub(r'\$\{([^}]+)\}', replace_env, value)


def _parse_custom_headers(headers_config: Optional[str]) -> Dict[str, str]:
    """Parse custom headers JSON using Ocean's Pydantic utilities and resolve environment variable references"""
    if not headers_config:
        return {}
    
    try:
        # Use Ocean's Pydantic parse_raw_as (same as used in Ocean's config parsing)
        headers_dict = parse_raw_as(Dict[str, Any], headers_config)
        
        # Resolve environment variable references in values
        resolved_headers = {}
        for key, value in headers_dict.items():
            if isinstance(value, str):
                resolved_headers[key] = _resolve_env_vars(value)
            else:
                resolved_headers[key] = str(value)
        
        return resolved_headers
    except Exception as e:
        raise ValueError(f"Invalid custom_headers JSON: {e}")


def init_client() -> HttpServerClient:
    """Initialize Ocean Custom client from Ocean configuration"""
    config = ocean.integration_config

    # Parse custom headers from config
    custom_headers = _parse_custom_headers(config.get("custom_headers"))

    return HttpServerClient(
        base_url=config["base_url"],
        auth_type=config.get("auth_type", "none"),
        auth_config=config,
        pagination_config=config,
        timeout=int(config.get("timeout", 30)),
        verify_ssl=config.get("verify_ssl", True),
        max_concurrent_requests=int(config.get("max_concurrent_requests", 10)),
        custom_headers=custom_headers,
    )
