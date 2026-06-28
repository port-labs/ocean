import asyncio
import typing

from loguru import logger

from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.issues import IssueState, IssuesHandler
from newrelic_integration.overrides import NewRelicPortAppConfig
from newrelic_integration.utils import (
    NewRelicAnyResourceConfig,
    get_port_resource_configuration_by_newrelic_entity_type,
)
from newrelic_integration.webhook.constants import (
    DEFAULT_ISSUE_KIND,
    ISSUE_ENTITY_TYPE,
    RESYNC_ONLY_KINDS,
)

_inflight_entity_fetches: dict[
    tuple[str, ...], asyncio.Task[dict[str, dict[str, typing.Any]]]
] = {}


def get_issue_kinds(app_config: NewRelicPortAppConfig) -> list[str]:
    kinds: list[str] = []
    for resource in app_config.resources:
        if resource.kind == DEFAULT_ISSUE_KIND:
            kinds.append(resource.kind)
        elif (
            resource.selector.newrelic_types
            and ISSUE_ENTITY_TYPE in resource.selector.newrelic_types
        ):
            kinds.append(resource.kind)
    return kinds or [DEFAULT_ISSUE_KIND]


def get_entity_kinds(app_config: NewRelicPortAppConfig) -> list[str]:
    kinds: list[str] = []
    for resource in app_config.resources:
        if resource.kind in RESYNC_ONLY_KINDS:
            continue
        if resource.kind == DEFAULT_ISSUE_KIND:
            continue
        if (
            resource.selector.newrelic_types
            and ISSUE_ENTITY_TYPE in resource.selector.newrelic_types
            and not resource.selector.entity_query_filter
        ):
            continue
        if resource.selector.entity_query_filter:
            kinds.append(resource.kind)
    return kinds


async def _load_entities_by_guids(
    entity_guids: list[str],
) -> dict[str, dict[str, typing.Any]]:
    entities = await EntitiesHandler().list_entities_by_guids(entity_guids)
    return {entity["guid"]: entity for entity in entities}


async def get_issue_event_entities(
    entity_guids: list[str],
) -> dict[str, dict[str, typing.Any]]:
    unique_guids = tuple(dict.fromkeys(guid for guid in entity_guids if guid))
    if not unique_guids:
        return {}

    fetch_key = unique_guids
    task = _inflight_entity_fetches.get(fetch_key)
    if task is None:
        task = asyncio.create_task(_load_entities_by_guids(list(unique_guids)))
        _inflight_entity_fetches[fetch_key] = task
        task.add_done_callback(
            lambda completed_task: (
                _inflight_entity_fetches.pop(fetch_key, None)
                if _inflight_entity_fetches.get(fetch_key) is completed_task
                else None
            )
        )

    entities_by_guid = await task
    return {
        entity_guid: entities_by_guid[entity_guid]
        for entity_guid in unique_guids
        if entity_guid in entities_by_guid
    }


async def enrich_issue_entity_relations(
    issue_record: dict[str, typing.Any],
) -> None:
    entity_guids = issue_record.get("entityGuids", [])
    try:
        entities_by_guid = await get_issue_event_entities(entity_guids)
    except Exception as err:
        logger.exception(
            "Failed to get entities for issue event, continuing",
            entity_guids=entity_guids,
            err=str(err),
        )
        return

    for entity_guid in entity_guids:
        try:
            entity = entities_by_guid.get(entity_guid)
            if entity is None:
                logger.warning(
                    "Failed to get entity for issue event, continuing",
                    entity_guid=entity_guid,
                )
                continue

            entity_type = entity["type"]
            entity_resource_config = (
                await get_port_resource_configuration_by_newrelic_entity_type(
                    entity_type
                )
            )
            if not entity_resource_config:
                logger.warning(
                    "Received issue event for unknown entity type, ignoring",
                    entity_type=entity_type,
                )
                continue

            issue_record.setdefault(f"__{entity_type}", {}).setdefault(
                "entity_guids", []
            ).append(entity_guid)
        except Exception as err:
            logger.exception(
                "Failed to get entity for issue event, continuing",
                entity_guid=entity_guid,
                err=str(err),
            )


async def fetch_entities_for_resource(
    resource_config: NewRelicAnyResourceConfig,
    entity_guids: list[str],
) -> list[dict[str, typing.Any]]:
    entity_query_filter = resource_config.selector.entity_query_filter
    if not entity_guids or not entity_query_filter:
        return []

    entities = await EntitiesHandler().list_entities_by_guids_and_filter(
        entity_guids,
        entity_query_filter,
        resource_config.selector.entity_extra_properties_query,
    )
    entities_by_guid = {entity["guid"]: entity for entity in entities}
    updated_entities: list[dict[str, typing.Any]] = []

    for entity_guid in entity_guids:
        entity = entities_by_guid.get(entity_guid)
        if entity is None:
            continue

        if resource_config.selector.calculate_open_issue_count:
            number_of_open_issues = (
                await IssuesHandler().get_number_of_issues_by_entity_guid(
                    entity_guid,
                    issue_state=IssueState.ACTIVATED,
                )
            )
            entity = {**entity, "__open_issues_count": number_of_open_issues}

        updated_entities.append(entity)

    return updated_entities
