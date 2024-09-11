import asyncio
from typing import Any
from urllib.parse import quote_plus

import httpx
from loguru import logger

from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.types import RequestOptions, UserAgentType
from port_ocean.clients.port.utils import (
    handle_status_code,
    PORT_HTTP_MAX_CONNECTIONS_LIMIT,
)
from port_ocean.core.models import Entity


class EntityClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client
        # Semaphore is used to limit the number of concurrent requests to port, to avoid overloading it.
        # The number of concurrent requests is set to 90% of the max connections limit, to leave some room for other
        # requests that are not related to entities.
        self.semaphore = asyncio.Semaphore(round(0.9 * PORT_HTTP_MAX_CONNECTIONS_LIMIT))

    async def upsert_entity(
        self,
        entity: Entity,
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> Entity | None:
        validation_only = request_options["validation_only"]
        async with self.semaphore:
            logger.debug(
                f"{'Validating' if validation_only else 'Upserting'} entity: {entity.identifier} of blueprint: {entity.blueprint}"
            )
            headers = await self.auth.headers(user_agent_type)
            response = await self.client.post(
                f"{self.auth.api_url}/blueprints/{entity.blueprint}/entities",
                json=entity.dict(exclude_unset=True, by_alias=True),
                headers=headers,
                params={
                    "upsert": "true",
                    "merge": str(request_options["merge"]).lower(),
                    "create_missing_related_entities": str(
                        request_options["create_missing_related_entities"]
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
        result = response.json()

        result_entity = (
            Entity.parse_obj(result["entity"]) if result.get("entity") else entity
        )

        # Happens when upsert fails and search identifier is defined.
        # We return None to ignore the entity later in the delete process
        if result_entity.is_using_search_identifier:
            return None

        # In order to save memory we'll keep only the identifier, blueprint and relations of the
        # upserted entity result for later calculations
        reduced_entity = Entity(
            identifier=result_entity.identifier, blueprint=result_entity.blueprint
        )

        # Turning dict typed relations (raw search relations) is required
        # for us to be able to successfully calculate the participation related entities
        # and ignore the ones that don't as they weren't upserted
        reduced_entity.relations = {
            key: None if isinstance(relation, dict) else relation
            for key, relation in result_entity.relations.items()
        }

        return reduced_entity

    async def batch_upsert_entities(
        self,
        entities: list[Entity],
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> list[Entity]:
        modified_entities_results = await asyncio.gather(
            *(
                self.upsert_entity(
                    entity,
                    request_options,
                    user_agent_type,
                    should_raise=should_raise,
                )
                for entity in entities
            ),
            return_exceptions=True,
        )
        entity_results = [
            entity for entity in modified_entities_results if isinstance(entity, Entity)
        ]
        if not should_raise:
            return entity_results

        for entity_result in modified_entities_results:
            if isinstance(entity_result, Exception):
                raise entity_result

        return entity_results

    async def delete_entity(
        self,
        entity: Entity,
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> None:
        async with self.semaphore:
            logger.info(
                f"Delete entity: {entity.identifier} of blueprint: {entity.blueprint}"
            )
            response = await self.client.delete(
                f"{self.auth.api_url}/blueprints/{entity.blueprint}/entities/{quote_plus(entity.identifier)}",
                headers=await self.auth.headers(user_agent_type),
                params={
                    "delete_dependents": str(
                        request_options["delete_dependent_entities"]
                    ).lower()
                },
            )

            if response.is_error:
                if response.status_code == 404:
                    logger.info(
                        f"Failed to delete entity: {entity.identifier} of blueprint: {entity.blueprint},"
                        f" as it was already deleted from port"
                    )
                    return
                logger.error(
                    f"Error deleting "
                    f"entity: {entity.identifier} of "
                    f"blueprint: {entity.blueprint}"
                )

            handle_status_code(response, should_raise)

    async def batch_delete_entities(
        self,
        entities: list[Entity],
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> None:
        await asyncio.gather(
            *(
                self.delete_entity(
                    entity,
                    request_options,
                    user_agent_type,
                    should_raise=should_raise,
                )
                for entity in entities
            ),
            return_exceptions=True,
        )

    async def search_entities(
        self, user_agent_type: UserAgentType, query: dict[Any, Any] | None = None
    ) -> list[Entity]:
        default_query = {
            "combinator": "and",
            "rules": [
                {
                    "property": "$datasource",
                    "operator": "contains",
                    "value": f"port-ocean/{self.auth.integration_type}/",
                },
                {
                    "property": "$datasource",
                    "operator": "contains",
                    "value": f"/{self.auth.integration_identifier}/{user_agent_type.value}",
                },
            ],
        }

        if query is None:
            query = default_query
        elif query.get("rules"):
            query["rules"].append(default_query)

        logger.info(f"Searching entities with query {query}")
        response = await self.client.post(
            f"{self.auth.api_url}/entities/search",
            json=query,
            headers=await self.auth.headers(user_agent_type),
            params={
                "exclude_calculated_properties": "true",
                "include": ["blueprint", "identifier"],
            },
            extensions={"retryable": True},
            timeout=30,
        )
        handle_status_code(response)
        return [Entity.parse_obj(result) for result in response.json()["entities"]]

    async def search_batch_entities(
        self, user_agent_type: UserAgentType, entities_to_search: list[Entity]
    ) -> list[Entity]:
        search_rules = []
        for entity in entities_to_search:
            search_rules.append(
                {
                    "combinator": "and",
                    "rules": [
                        {
                            "property": "$identifier",
                            "operator": "=",
                            "value": entity.identifier,
                        },
                        {
                            "property": "$blueprint",
                            "operator": "=",
                            "value": entity.blueprint,
                        },
                    ],
                }
            )

        return await self.search_entities(
            user_agent_type,
            {
                "combinator": "and",
                "rules": [{"combinator": "or", "rules": search_rules}],
            },
        )
