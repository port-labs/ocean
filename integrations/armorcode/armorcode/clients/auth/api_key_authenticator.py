from typing import Dict, Any
from .abstract_authenticator import AbstractArmorcodeAuthenticator


class ApiKeyAuthenticator(AbstractArmorcodeAuthenticator):
    """API Key authentication for ArmorCode."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def get_headers(self) -> Dict[str, str]:
        """Get API key authentication headers."""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

    def get_auth_params(self) -> Dict[str, Any]:
        """Get authentication parameters (empty for API key auth)."""
        return {}
