import asyncio
from typing import Any, Literal
from urllib.parse import quote_plus
import json

import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.clients.port.authentication import PortAuthentication
from port_ocean.clients.port.types import RequestOptions, UserAgentType
from port_ocean.clients.port.utils import (
    handle_port_status_code,
    PORT_HTTP_MAX_CONNECTIONS_LIMIT,
)
from port_ocean.core.models import (
    BulkUpsertResponse,
    Entity,
    PortAPIErrorMessage,
)
from starlette import status

from port_ocean.helpers.metric.metric import MetricPhase, MetricType

ENTITIES_BULK_SAMPLES_SIZE = 10
ENTITIES_BULK_ESTIMATED_SIZE_MULTIPLIER = 1.5
ENTITIES_BULK_MINIMUM_BATCH_SIZE = 1


class EntityClientMixin:
    def __init__(self, auth: PortAuthentication, client: httpx.AsyncClient):
        self.auth = auth
        self.client = client
        # Semaphore is used to limit the number of concurrent requests to port, to avoid overloading it.
        # The number of concurrent requests is set to 90% of the max connections limit, to leave some room for other
        # requests that are not related to entities.
        self.semaphore = asyncio.Semaphore(
            round(0.5 * PORT_HTTP_MAX_CONNECTIONS_LIMIT)
        )  # 50% of the max connections limit in order to avoid overloading port

    def calculate_entities_batch_size(self, entities: list[Entity]) -> int:
        """
        Calculate the optimal batch size based on entity size and configured limits.

        Args:
            entities: List of entities to calculate batch size for

        Returns:
            int: The optimal batch size to use
        """
        if not entities:
            return ENTITIES_BULK_MINIMUM_BATCH_SIZE

        # Calculate average entity size from a sample
        SAMPLE_SIZE = min(ENTITIES_BULK_SAMPLES_SIZE, len(entities))
        sample_entities = entities[:SAMPLE_SIZE]
        average_entity_size = (
            sum(
                len(json.dumps(entity.dict(exclude_unset=True, by_alias=True)).encode())
                for entity in sample_entities
            )
            / SAMPLE_SIZE
        )

        # Use a conservative estimate to ensure we stay under the limit
        estimated_entity_size = int(
            average_entity_size * ENTITIES_BULK_ESTIMATED_SIZE_MULTIPLIER
        )
        max_entities_per_batch = min(
            ocean.config.upsert_entities_batch_max_length,
            ocean.config.upsert_entities_batch_max_size_in_bytes
            // estimated_entity_size,
        )

        return max(ENTITIES_BULK_MINIMUM_BATCH_SIZE, max_entities_per_batch)

    async def upsert_entity(
        self,
        entity: Entity,
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> Entity | None | Literal[False]:
        """
        This function upserts an entity into Port.

        Usage:
        ```python
            upsertedEntity = await self.context.port_client.upsert_entity(
                            entity,
                            event.port_app_config.get_port_request_options(),
                            user_agent_type,
                            should_raise=False,
                        )
        ```
        :param entity: An Entity to be upserted
        :param request_options: A dictionary specifying how to upsert the entity
        :param user_agent_type: a UserAgentType specifying who is preforming the action
        :param should_raise: A boolean specifying whether the error should be raised or handled silently
        :return: [Entity] if the upsert occured successfully
        :return: [None] will be returned if entity is using search identifier
        :return: [False] will be returned if upsert failed because of unmet dependency
        """
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
                extensions={"retryable": True},
            )
        if response.is_error:
            logger.error(
                f"Error {'Validating' if validation_only else 'Upserting'} "
                f"entity: {entity.identifier} of "
                f"blueprint: {entity.blueprint}"
            )
            result = response.json()
            ocean.metrics.inc_metric(
                name=MetricType.OBJECT_COUNT_NAME,
                labels=[
                    ocean.metrics.current_resource_kind(),
                    MetricPhase.LOAD,
                    MetricPhase.LoadResult.FAILED,
                ],
                value=1,
            )

            if (
                response.status_code == status.HTTP_404_NOT_FOUND
                and not result.get("ok")
                and result.get("error") == PortAPIErrorMessage.NOT_FOUND.value
            ):
                # Return false to differentiate from `result_entity.is_using_search_identifier`
                return False
        else:
            ocean.metrics.inc_metric(
                name=MetricType.OBJECT_COUNT_NAME,
                labels=[
                    ocean.metrics.current_resource_kind(),
                    MetricPhase.LOAD,
                    MetricPhase.LoadResult.LOADED,
                ],
                value=1,
            )

        handle_port_status_code(response, should_raise)
        result = response.json()

        result_entity = (
            Entity.parse_obj(result["entity"]) if result.get("entity") else entity
        )

        # Happens when upsert fails and search identifier is defined.
        # We return None to ignore the entity later in the delete process
        if result_entity.is_using_search_identifier:
            return None
        return self._reduce_entity(result_entity)

    async def upsert_entities_bulk(
        self,
        blueprint: str,
        entities: list[Entity],
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> list[tuple[bool | None, Entity]] | httpx.HTTPStatusError:
        """
        This function upserts a list of entities into Port.

        Usage:
        ```python
            upsertedEntities = await self.context.port_client.upsert_entities_batch(
                            entities,
                            event.port_app_config.get_port_request_options(),
                            user_agent_type,
                            should_raise=False,
                        )
        ```
        :param blueprint: The blueprint of the entities to be upserted
        :param entities: A list of Entities to be upserted
        :param request_options: A dictionary specifying how to upsert the entity
        :param user_agent_type: a UserAgentType specifying who is preforming the action
        :param should_raise: A boolean specifying whether the error should be raised or handled silently
        :return: A list of tuples where each tuple contains:
            - First value: True if entity was created successfully, False if there was an error, None if there was an error and the entity use search identifier
            - Second value: The original entity (if failed) or the reduced entity with updated identifier (if successful)
        :return: httpx.HTTPStatusError if there was an HTTP error and should_raise is False
        """
        validation_only = request_options["validation_only"]
        async with self.semaphore:
            logger.debug(
                f"{'Validating' if validation_only else 'Upserting'} {len(entities)} of blueprint: {blueprint}"
            )
            headers = await self.auth.headers(user_agent_type)
            response = await self.client.post(
                f"{self.auth.api_url}/blueprints/{blueprint}/entities/bulk",
                json={
                    "entities": [
                        entity.dict(exclude_unset=True, by_alias=True)
                        for entity in entities
                    ]
                },
                headers=headers,
                params={
                    "upsert": "true",
                    "merge": str(request_options["merge"]).lower(),
                    "create_missing_related_entities": str(
                        request_options["create_missing_related_entities"]
                    ).lower(),
                    "validation_only": str(validation_only).lower(),
                },
                extensions={"retryable": True},
            )
        if response.is_error:
            logger.error(
                f"Error {'Validating' if validation_only else 'Upserting'} "
                f"{len(entities)} entities of "
                f"blueprint: {blueprint}"
            )
            handle_port_status_code(response, should_raise)
            return httpx.HTTPStatusError(
                f"HTTP {response.status_code}",
                request=response.request,
                response=response,
            )
        handle_port_status_code(response, should_raise)
        result = response.json()

        return self._parse_upsert_entities_batch_response(entities, result)

    def _parse_upsert_entities_batch_response(
        self,
        entities: list[Entity],
        result: BulkUpsertResponse,
    ) -> list[tuple[bool | None, Entity]]:
        """
        Parse the response from a bulk upsert operation and map it to the original entities.

        :param entities: The original entities
        :param result: The response from the bulk upsert operation
        :return: A list of tuples containing the success status and the entity
        """
        index_to_entity = {i: entity for i, entity in enumerate(entities)}
        successful_entities = {
            entity_result["index"]: entity_result
            for entity_result in result.get("entities", [])
        }
        error_entities = {error["index"]: error for error in result.get("errors", [])}

        batch_results: list[tuple[bool | None, Entity]] = []
        for entity_index, original_entity in index_to_entity.items():
            reduced_entity = self._reduce_entity(original_entity)
            if entity_index in successful_entities:
                ocean.metrics.inc_metric(
                    name=MetricType.OBJECT_COUNT_NAME,
                    labels=[
                        ocean.metrics.current_resource_kind(),
                        MetricPhase.LOAD,
                        MetricPhase.LoadResult.LOADED,
                    ],
                    value=1,
                )
                success_entity = successful_entities[entity_index]
                # Create a copy of the original entity with the new identifier
                updated_entity = reduced_entity.copy()
                updated_entity.identifier = success_entity["identifier"]
                batch_results.append((True, updated_entity))
            elif entity_index in error_entities:
                ocean.metrics.inc_metric(
                    name=MetricType.OBJECT_COUNT_NAME,
                    labels=[
                        ocean.metrics.current_resource_kind(),
                        MetricPhase.LOAD,
                        MetricPhase.LoadResult.FAILED,
                    ],
                    value=1,
                )
                error = error_entities[entity_index]
                if (
                    error.get("identifier") == "unknown"
                ):  # when using the search identifier we might not have an actual identifier
                    batch_results.append((None, reduced_entity))
                else:
                    batch_results.append((False, reduced_entity))
            else:
                batch_results.append((False, reduced_entity))

        return batch_results

    async def _upsert_entities_batch_individually(
        self,
        entities: list[Entity],
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> list[tuple[bool, Entity]]:
        entities_results: list[tuple[bool, Entity]] = []
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

        for original_entity, single_result in zip(entities, modified_entities_results):
            if isinstance(single_result, Exception) and should_raise:
                raise single_result
            elif isinstance(single_result, Entity):
                entities_results.append((True, single_result))
            elif single_result is False:
                entities_results.append((False, original_entity))

        return entities_results

    async def upsert_entities_in_batches(
        self,
        entities: list[Entity],
        request_options: RequestOptions,
        user_agent_type: UserAgentType | None = None,
        should_raise: bool = True,
    ) -> list[tuple[bool, Entity]]:
        """
        This function upserts a list of entities into Port in batches.
        The batch size is calculated based on both the number of entities and their size.
        Batches are processed in parallel using asyncio.gather, with concurrency controlled by the semaphore.

        :param entities: A list of Entities to be upserted
        :param request_options: A dictionary specifying how to upsert the entity
        :param user_agent_type: a UserAgentType specifying who is preforming the action
        :param should_raise: A boolean specifying whether the error should be raised or handled silently
        :return: A list of tuples where each tuple contains:
            - First value: True if entity was created successfully, False if there was an error
            - Second value: The reduced entity with updated identifier (if successful) or the original entity (if failed)
        """
        entities_results: list[tuple[bool, Entity]] = []
        blueprint = entities[0].blueprint

        if ocean.config.bulk_upserts_enabled:
            bulk_size = self.calculate_entities_batch_size(entities)
            bulks = [
                entities[i : i + bulk_size] for i in range(0, len(entities), bulk_size)
            ]

            bulk_results = await asyncio.gather(
                *(
                    self.upsert_entities_bulk(
                        blueprint,
                        bulk,
                        request_options,
                        user_agent_type,
                        should_raise=should_raise,
                    )
                    for bulk in bulks
                ),
                return_exceptions=True,
            )

            for bulk, bulk_result in zip(bulks, bulk_results):
                if isinstance(bulk_result, httpx.HTTPStatusError) or isinstance(
                    bulk_result, Exception
                ):
                    if should_raise:
                        raise bulk_result
                    # If should_raise is False, retry batch in sequential order as a fallback only for 413 errors
                    if (
                        isinstance(bulk_result, httpx.HTTPStatusError)
                        and bulk_result.response.status_code == 413
                    ):
                        individual_upsert_results = (
                            await self._upsert_entities_batch_individually(
                                bulk, request_options, user_agent_type, should_raise
                            )
                        )
                        entities_results.extend(individual_upsert_results)
                    else:
                        # For other errors, mark all entities in the batch as failed
                        for entity in bulk:
                            failed_result: tuple[bool, Entity] = (
                                False,
                                self._reduce_entity(entity),
                            )
                            entities_results.append(failed_result)
                elif isinstance(bulk_result, list):
                    for status, entity in bulk_result:
                        if (
                            status is not None
                        ):  # when using the search identifier we might not have an actual identifier
                            bulk_result_tuple: tuple[bool, Entity] = (
                                bool(status),
                                entity,
                            )
                            entities_results.append(bulk_result_tuple)
        else:
            individual_upsert_results = await self._upsert_entities_batch_individually(
                entities, request_options, user_agent_type, should_raise
            )
            entities_results.extend(individual_upsert_results)

        return entities_results

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

            handle_port_status_code(response, should_raise)

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
        self,
        user_agent_type: UserAgentType,
        query: dict[Any, Any] | None = None,
        parameters_to_include: list[str] | None = None,
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
                "include": parameters_to_include or ["blueprint", "identifier"],
            },
            extensions={"retryable": True},
        )
        handle_port_status_code(response)
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

    @staticmethod
    def _reduce_entity(entity: Entity) -> Entity:
        """
        Reduces an entity to only keep identifier, blueprint and processed relations.
        This helps save memory by removing unnecessary data.

        Args:
            entity: The entity to reduce

        Returns:
            Entity: A new entity with only the essential data
        """
        reduced_entity = Entity(
            identifier=entity.identifier, blueprint=entity.blueprint
        )

        # Turning dict typed relations (raw search relations) is required
        # for us to be able to successfully calculate the participation related entities
        # and ignore the ones that don't as they weren't upserted
        reduced_entity.relations = {
            key: None if isinstance(relation, dict) else relation
            for key, relation in entity.relations.items()
        }
        return reduced_entity
