from armorcode.clients.auth.abstract_authenticator import (
    AbstractArmorcodeAuthenticator,
    ArmorcodeHeaders,
)


class ApiKeyAuthenticator(AbstractArmorcodeAuthenticator):
    """API Key authentication for ArmorCode."""

    def __init__(self, api_key: str):
        self.api_key = api_key

    async def get_headers(self) -> ArmorcodeHeaders:
        """Get API key authentication headers."""
        return ArmorcodeHeaders(
            Authorization=f"Bearer {self.api_key}",
            Accept="application/json",
            **{"Content-Type": "application/json"},
        )
