from urllib.parse import quote_plus

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.types import RequestOptions, UserAgentType
from port_ocean.clients.port.utils import handle_status_code
from port_ocean.core.models import Entity


class EntityClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client

    async def upsert_entity(
        self,
        entity: Entity,
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> None:
        validation_only = request_options.get("validation_only", False)
        logger.info(
            f"{'Validating' if validation_only else 'Upserting'} entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )
        headers = await self.auth.headers(user_agent_type)

        response = await self.client.post(
            f"{self.auth.api_url}/blueprints/{entity.blueprint}/entities",
            json=entity.dict(exclude_unset=True, by_alias=True),
            headers=headers,
            params={
                "upsert": "true",
                "merge": str(request_options.get("merge", False)).lower(),
                "create_missing_related_entities": str(
                    request_options.get("create_missing_related_entities", False)
                ).lower(),
                "validation_only": str(validation_only).lower(),
            },
        )

        if response.is_error:
            logger.error(
                f"Error {'Validating' if validation_only else 'Upserting'} "
                f"entity: {entity.identifier} of "
                f"blueprint: {entity.blueprint}"
            )
        handle_status_code(response, should_raise)

    async def delete_entity(
        self,
        entity: Entity,
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> None:
        logger.info(
            f"Delete entity: {entity.identifier} of blueprint: {entity.blueprint}"
        )
        response = await self.client.delete(
            f"{self.auth.api_url}/blueprints/{entity.blueprint}/entities/{quote_plus(entity.identifier)}",
            headers=await self.auth.headers(user_agent_type),
            params={
                "delete_dependents": str(
                    request_options.get("delete_dependent_entities", False)
                ).lower()
            },
        )

        if response.is_error:
            logger.error(
                f"Error deleting "
                f"entity: {entity.identifier} of "
                f"blueprint: {entity.blueprint}"
            )

        handle_status_code(response, should_raise)

    async def validate_entity_exist(self, identifier: str, blueprint: str) -> None:
        logger.info(f"Validating entity {identifier} of blueprint {blueprint} exists")

        response = await self.client.get(
            f"{self.auth.api_url}/blueprints/{blueprint}/entities/{identifier}",
            headers=await self.auth.headers(),
        )
        if response.is_error:
            logger.error(
                f"Error validating "
                f"entity: {identifier} of "
                f"blueprint: {blueprint}"
            )
        handle_status_code(response)

    async def search_entities(self, user_agent_type: UserAgentType) -> list[Entity]:
        query = {
            "combinator": "and",
            "rules": [
                {
                    "property": "$datasource",
                    "operator": "=",
                    "value": self.auth.user_agent(user_agent_type),
                },
            ],
        }

        logger.info(f"Searching entities with query {query}")
        response = await self.client.post(
            f"{self.auth.api_url}/entities/search",
            json=query,
            headers=await self.auth.headers(user_agent_type),
            params={
                "exclude_calculated_properties": "true",
                "include": ["blueprint", "identifier"],
            },
        )
        handle_status_code(response)
        return [Entity.parse_obj(result) for result in response.json()["entities"]]

    async def search_dependent_entities(self, entity: Entity) -> list[Entity]:
        body = {
            "combinator": "and",
            "rules": [
                {
                    "operator": "relatedTo",
                    "blueprint": entity.blueprint,
                    "value": entity.identifier,
                    "direction": "downstream",
                }
            ],
        }

        logger.info(f"Searching dependent entity with body {body}")
        response = await self.client.post(
            f"{self.auth.api_url}/entities/search",
            headers=await self.auth.headers(),
            json=body,
        )
        handle_status_code(response)

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
