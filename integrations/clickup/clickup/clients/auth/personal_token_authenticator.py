from clickup.clients.auth.abstract_authenticator import (
    AbstractClickUpAuthenticator,
    ClickUpHeaders,
)


class PersonalTokenAuthenticator(AbstractClickUpAuthenticator):
    """Personal API Token authentication for ClickUp.

    ClickUp personal tokens begin with 'pk_' and are passed directly
    in the Authorization header without a 'Bearer' prefix.

    Reference: https://developer.clickup.com/docs/authentication#personal-token
    """

    def __init__(self, api_token: str) -> None:
        self.api_token = api_token

    async def get_headers(self) -> ClickUpHeaders:
        """Get personal token authentication headers."""
        return ClickUpHeaders(Authorization=self.api_token)
