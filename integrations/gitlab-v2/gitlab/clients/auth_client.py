from port_ocean.clients.auth.oauth_client import OAuthClient
import httpx


class AuthClient(OAuthClient):
    def __init__(self, token: str):
        self.token = token

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        try:
            auth_token = self.external_access_token
        except ValueError:
            auth_token = self.token
        request.headers["Authorization"] = auth_token
        return request

    def get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def get_refreshed_token(self) -> str:
        """Get a refreshed external access token"""
        return self.external_access_token
