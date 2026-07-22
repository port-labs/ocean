import base64

from auth.abstract_authenticator import AbstractServiceNowAuthenticator


class BasicAuthenticator(AbstractServiceNowAuthenticator):
    """Authenticator using Basic Auth with username and password."""

    def __init__(self, username: str, password: str):
        self.username = username
        self.password = password

    async def get_headers(self) -> dict[str, str]:
        auth_message = f"{self.username}:{self.password}"
        auth_bytes = auth_message.encode("ascii")
        b64_bytes = base64.standard_b64encode(auth_bytes)
        b64_message = b64_bytes.decode("ascii")

        return {
            "Authorization": f"Basic {b64_message}",
            "Content-Type": "application/json",
        }
