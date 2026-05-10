from httpx import AsyncClient, BasicAuth

from azure_devops.client.auth.base import Authenticator


class PersonalAccessTokenAuthenticator(Authenticator):
    """Legacy single-org authentication using a Personal Access Token."""

    def __init__(self, personal_access_token: str) -> None:
        self._personal_access_token = personal_access_token

    async def apply(self, client: AsyncClient) -> None:
        client.auth = BasicAuth("", self._personal_access_token)
