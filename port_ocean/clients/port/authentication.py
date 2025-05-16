import re
from typing import Any

import httpx
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

from port_ocean.clients.port.types import UserAgentType
from port_ocean.clients.port.utils import handle_port_status_code
from port_ocean.utils.misc import get_time


class TokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    expires_in: int = Field(alias="expiresIn")
    token_type: str = Field(alias="tokenType")
    _retrieved_time: int = PrivateAttr(default_factory=lambda: int(get_time()))

    @property
    def expired(self) -> bool:
        return self._retrieved_time + self.expires_in <= get_time()

    @property
    def full_token(self) -> str:
        return f"{self.token_type} {self.access_token}"


class PortAuthentication:
    def __init__(
        self,
        client: httpx.AsyncClient,
        client_id: str,
        client_secret: str,
        api_url: str,
        integration_identifier: str,
        integration_type: str,
        integration_version: str,
    ):
        self.client = client
        self.api_url = api_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.integration_identifier = integration_identifier
        self.integration_type = integration_type
        self.integration_version = integration_version
        self.last_token_object: TokenResponse | None = None

    async def _get_token(self, client_id: str, client_secret: str) -> TokenResponse:
        logger.info(f"Fetching access token for clientId: {client_id}")
        if self._is_personal_token(client_id):
            logger.warning(
                "Integration is using personal credentials, make sure to use machine credentials. "
                "Usage of personal credentials might impose unexpected integration behavior."
            )
        credentials = {"clientId": client_id, "clientSecret": client_secret}
        response = await self.client.post(
            f"{self.api_url}/auth/access_token",
            json=credentials,
            extensions={"retryable": True},
        )
        handle_port_status_code(response)
        return TokenResponse(**response.json())

    def user_agent(self, user_agent_type: UserAgentType | None = None) -> str:
        user_agent = f"port-ocean/{self.integration_type}/{self.integration_version}/{self.integration_identifier}"
        if user_agent_type:
            user_agent += f"/{user_agent_type.value or UserAgentType.exporter.value}"

        return user_agent

    async def headers(
        self, user_agent_type: UserAgentType | None = None
    ) -> dict[Any, Any]:
        return {
            "Authorization": await self.token,
            "User-Agent": self.user_agent(user_agent_type),
        }

    @property
    async def token(self) -> str:
        if not self.last_token_object or self.last_token_object.expired:
            msg = "Token expired, fetching new token"
            if not self.last_token_object:
                msg = "No token found, fetching new token"
            logger.info(msg)
            self.last_token_object = await self._get_token(
                self.client_id, self.client_secret
            )
        return self.last_token_object.full_token

    @staticmethod
    def _is_personal_token(client_id: str) -> bool:
        email_regex = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
        return re.match(email_regex, client_id) is not None
