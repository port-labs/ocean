from datetime import datetime
from typing import Dict, Any, List

import httpx as httpx
from loguru import logger
from pydantic import BaseModel, Field, PrivateAttr

from port_ocean.clients.port.types import (
    KafkaCreds,
    ChangelogDestination,
    RequestOptions,
)
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.models import Entity, Blueprint


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

    async def _get_token(self, client_id: str, client_secret: str) -> TokenResponse:
        async with httpx.AsyncClient() as client:
            logger.info(f"Fetching access token for clientId: {client_id}")

            credentials = {"clientId": client_id, "clientSecret": client_secret}
            token_response = await client.post(
                f"{self.api_url}/auth/access_token", json=credentials
            )
            token_response.raise_for_status()
            return TokenResponse(**token_response.json())

    @property
    async def headers(self) -> Dict[Any, Any]:
        return {
            "Authorization": await self.token,
            "User-Agent": self.user_agent,
        }

    @property
    async def token(self) -> str:
        logger.info("Fetching access token")
        if not self._last_token_object or self._last_token_object.expired:
            self._last_token_object = await self._get_token(
                self.client_id, self.client_secret
            )
        else:
            logger.info("Access token found in cache")

        return self._last_token_object.full_token

    async def upsert_entity(
        self, entity: Entity, request_options: RequestOptions
    ) -> None:
        validation_only = request_options.get("validation_only", False)
        logger.info(
            f"{'Validating' if validation_only else 'Upserting'} entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/blueprints/{entity.blueprint}/entities",
                json=entity.dict(exclude_unset=True),
                headers=await self.headers,
                params={
                    "upsert": "true",
                    "merge": str(request_options.get("merge", False)).lower(),
                    "create_missing_related_entities": str(
                        request_options.get("create_missing_related_entities", False)
                    ).lower(),
                    "validation_only": str(validation_only).lower(),
                },
            )

        if not response.status_code < 400:
            logger.error(
                f"Error upserting "
                f"entity: {entity.identifier} of "
                f"blueprint: {entity.blueprint}, "
                f"error: {response.text}"
            )
            response.raise_for_status()

    async def delete_entity(self, entity: Entity) -> None:
        logger.info(
            f"Delete entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )
        async with httpx.AsyncClient() as client:
            response = await client.delete(
                f"{self.api_url}/blueprints/{entity.blueprint}/entities/{entity.identifier}",
                headers=await self.headers,
                params={"delete_dependents": "true"},
            )

        if not response.status_code < 400:
            logger.error(
                f"Error deleting "
                f"entity: {entity.identifier} of "
                f"blueprint: {entity.blueprint}, "
                f"error: {response.text}"
            )
            response.raise_for_status()

    async def get_kafka_creds(self) -> KafkaCreds:
        logger.info("Fetching organization kafka credentials")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/kafka-credentials", headers=await self.headers
            )
        if not response.status_code < 400:
            logger.error(f"Error getting kafka credentials, error: {response.text}")
            response.raise_for_status()

        credentials = response.json()["credentials"]

        if credentials is None:
            raise Exception("No kafka credentials found")

        return credentials

    async def get_org_id(self) -> str:
        logger.info("Fetching organization id")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/organization", headers=await self.headers
            )
        if not response.status_code < 400:
            logger.error(f"Error getting organization id, error: {response.text}")
            response.raise_for_status()

        return response.json()["organization"]["id"]

    async def validate_entity_exist(self, identifier: str, blueprint: str) -> None:
        logger.info(f"Validating entity {identifier} of blueprint {blueprint} exists")

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/v1/blueprints/{blueprint}/entities/{identifier}",
                headers=await self.headers,
            )
        response.raise_for_status()

    async def search_dependent_entities(self, entity: Entity) -> List[Entity]:
        body = {
            "combinator": "and",
            "rules": [
                {
                    "operator": "relatedTo",
                    "blueprint": entity.blueprint,
                    "value": entity.identifier,
                    "required": "true",
                    "direction": "downstream",
                }
            ],
        }

        logger.info(f"Search dependent entity with body {body}")
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/v1/entities/search",
                headers=await self.headers,
                json=body,
            )
        response.raise_for_status()

        return [Entity.parse_obj(result) for result in response.json()["entities"]]

    async def validate_entity_payload(
        self, entity: Entity, options: RequestOptions
    ) -> None:
        logger.info(f"Validating entity {entity.identifier}")
        await self.upsert_entity(
            entity,
            {
                "merge": options.get("merge", False),
                "create_missing_related_entities": options.get(
                    "create_missing_related_entities", False
                ),
                "validation_only": True,
            },
        )

    async def get_integration(self, identifier: str) -> PortAppConfig:
        logger.info(f"Fetching integration with id: {identifier}")
        async with httpx.AsyncClient() as client:
            integration = await client.get(
                f"{self.api_url}/integration/{identifier}", headers=await self.headers
            )
        integration.raise_for_status()
        return PortAppConfig.parse_obj(integration.json()["integration"]["config"])

    async def initiate_integration(
        self, _id: str, _type: str, changelog_destination: ChangelogDestination
    ) -> None:
        logger.info(f"Initiating integration with id: {_id}")
        async with httpx.AsyncClient() as client:
            installation = await client.post(
                f"{self.api_url}/integration",
                headers=await self.headers,
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
        logger.info(f"Integration with id: {_id} successfully registered")

    async def get_blueprint(self, identifier: str) -> Blueprint:
        logger.info(f"Fetching blueprint with id: {identifier}")
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/v1/blueprints/{identifier}", headers=await self.headers
            )
        response.raise_for_status()
        return Blueprint.parse_obj(response.json()["blueprint"])
