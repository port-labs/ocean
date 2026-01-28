"""
Custom authentication handler with dynamic token retrieval and template evaluation.

Supports custom authentication flows with template-based token injection into requests.
"""

from typing import Dict, Any
import httpx

from http_server.auth.base import AuthHandler
from http_server.helpers.auth_validation import (
    validate_custom_auth_request_config,
    validate_custom_auth_response_config,
)
from http_server.auth.custom_helpers.auth_flow import AuthFlowManager


class CustomAuth(AuthHandler):
    """Custom authentication handler"""

    def __init__(
        self,
        client: httpx.AsyncClient,
        config: Dict[str, Any],
    ):
        super().__init__(client, config)
        custom_auth_request = validate_custom_auth_request_config(
            config.get("custom_auth_request")
        )
        custom_auth_response = validate_custom_auth_response_config(
            config.get("custom_auth_response")
        )
        self.custom_auth = AuthFlowManager(
            config, custom_auth_request, custom_auth_response
        )

    def setup(self) -> None:
        """Setup authentication"""
        self.client.auth = self.custom_auth
