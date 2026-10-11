from port_ocean.clients.auth.oauth_client import OAuthClient
import httpx


class AuthClient(OAuthClient):
    def __init__(self, token: str):
        self.token = token
        self._allow_token_refresh = True

    def disable_token_refresh(self) -> None:
        """Bind this client to its current token; do not adopt integration OAuth."""
        self._allow_token_refresh = False

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        if self._allow_token_refresh:
            try:
                auth_token = self.external_access_token
            except ValueError:
                auth_token = self.token
        else:
            auth_token = self.token
        request.headers["Authorization"] = f"Bearer {auth_token}"
        return request

    def get_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json",
        }

    def get_refreshed_token(self) -> str:
        """Get a refreshed external access token"""
        if not self._allow_token_refresh:
            raise ValueError(
                "Token refresh is disabled for this client (identity-propagated token)"
            )
        return self.external_access_token
