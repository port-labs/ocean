import logging
from datetime import datetime
from typing import TypedDict, Dict, Any

import requests
from pydantic import BaseModel, Field, PrivateAttr

from port_ocean.models.port import Entity

logger = logging.getLogger(__name__)

Headers = TypedDict(
    "Headers",
    {
        "Authorization": str,
        "User-Agent": str,
    },
)

KafkaCreds = TypedDict(
    "KafkaCreds",
    {
        "username": str,
        "password": str,
    },
)


class TokenResponse(BaseModel):
    access_token: str = Field(alias="accessToken")
    expires_in: int = Field(alias="expiresIn")
    token_type: str = Field(alias="tokenType")
    _retrieved_time: datetime = PrivateAttr(datetime.now())

    @property
    def expired(self) -> bool:
        return (
            self._retrieved_time.timestamp() + self.expires_in
            < datetime.now().timestamp()
        )

    @property
    def full_token(self) -> str:
        return f"{self.token_type} {self.access_token}"


class PortClient:
    def __init__(
        self, base_url: str, client_id: str, client_secret: str, user_agent: str
    ):
        self.api_url = base_url
        self.client_id = client_id
        self.client_secret = client_secret
        self.user_agent = user_agent
        self._last_token_object: TokenResponse | None = None

    def _get_token(self, client_id: str, client_secret: str) -> TokenResponse:
        logger.info(f"Get access token for client: {client_id}")

        credentials = {"clientId": client_id, "clientSecret": client_secret}
        token_response = requests.post(
            f"{self.api_url}/auth/access_token", json=credentials
        )
        token_response.raise_for_status()
        return TokenResponse(**token_response.json())

    @property
    def headers(self) -> Dict[Any, Any]:
        return {
            "Authorization": self.token,
            "User-Agent": self.user_agent,
        }

    @property
    def token(self) -> str:
        if not self._last_token_object or self._last_token_object.expired:
            self._last_token_object = self._get_token(
                self.client_id, self.client_secret
            )

        return self._last_token_object.full_token

    async def upsert_entity(self, entity: Entity) -> None:
        logger.info(
            f"Upsert entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )

        response = requests.post(
            f"{self.api_url}/blueprints/{entity.blueprint}/entities",
            json=entity.to_api_dict(),
            headers=self.headers,
            params={"upsert": "true", "merge": "true"},
        )

        if not response.ok:
            logger.error(
                f"Error upserting entity: {entity.identifier} of blueprint: {entity.blueprint}, error: {response.text}"
            )
            response.raise_for_status()

    async def delete_entity(self, entity: Entity) -> None:
        logger.info(
            f"Delete entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )

        logger.info(
            f"Delete entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )
        response = requests.delete(
            f"{self.api_url}/blueprints/{entity.blueprint}/entities/{entity.identifier}",
            headers=self.headers,
            params={"delete_dependents": "true"},
        )

        if not response.ok:
            logger.error(
                f"Error deleting entity: {entity.identifier} of blueprint: {entity.blueprint}, error: {response.text}"
            )
            response.raise_for_status()

    async def get_kafka_creds(self) -> KafkaCreds:
        logger.info(f"Get kafka credentials")

        response = requests.get(
            f"{self.api_url}/kafka-credentials", headers=self.headers
        )
        if not response.ok:
            logger.error(f"Error getting kafka credentials, error: {response.text}")
            response.raise_for_status()

        return response.json()

    async def get_org_id(self) -> str:
        logger.info(f"Get organization id")

        response = requests.get(f"{self.api_url}/organization", headers=self.headers)
        if not response.ok:
            logger.error(f"Error getting organization id, error: {response.text}")
            response.raise_for_status()

        return response.json()["organization"]["id"]

    async def get_integration(self, identifier: str) -> Dict[Any, Any]:
        logger.info(f"Get integration with id: {identifier}")

        integration = requests.get(
            f"{self.api_url}/integration/{identifier}", headers=self.headers
        )
        integration.raise_for_status()

        return integration.json()

    async def initiate_integration(
        self, _id: str, _type: str, changelog_destination: Dict[Any, Any]
    ) -> None:
        logger.info(f"Initiate integration with id: {_id}")

        installation = requests.post(
            f"{self.api_url}/integration",
            headers=self.headers,
            json={
                "installationId": _id,
                "installationAppType": _type,
                "changelogDestination": changelog_destination,
            },
        )

        if installation.status_code == 409:
            logger.info(
                f"Integration with id: {_id} already exists, skipping registration"
            )

            return
        installation.raise_for_status()
