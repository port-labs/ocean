from typing import Any, Optional
import httpx
from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean


class AuthClient(OAuthClient):
    def __init__(self, personal_access_token: str):
        super().__init__()
        self.personal_access_token = personal_access_token

    def is_oauth_enabled(self) -> bool:
        """
        Safely determine whether OAuth is enabled for the current integration.

        Falls back to False when Ocean app/config are not initialized
        to preserve existing behavior in non-OAuth environments.
        """
        app = getattr(ocean, "app", None)
        config = getattr(app, "config", None) if app is not None else None
        return bool(getattr(config, "oauth_access_token_file_path", None))

    def get_headers(self, headers: Optional[dict[str, Any]] = None) -> dict[str, Any]:
        """
        Get headers with proper authentication.
        Falls back to PAT if OAuth token is not available (e.g., at app startup).
        """
        headers = headers or {}
        if self.is_oauth_enabled():
            try:
                access_token = self.external_access_token
                if access_token:
                    access_token = access_token.strip()
                    headers["Authorization"] = f"Bearer {access_token}"
            except ValueError:
                pass
        return headers

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        """
        Refresh Authorization header on retries when OAuth is enabled.
        Falls back to PAT if OAuth token is not available (e.g., at app startup).
        """
        if not self.is_oauth_enabled():
            return request

        try:
            access_token = self.external_access_token
            request.headers["Authorization"] = f"Bearer {access_token}"
        except ValueError:
            pass
        return request
