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
    return [
        resource.kind
        for resource in app_config.resources
        if resource.selector.entity_query_filter
        and resource.kind not in RESYNC_ONLY_KINDS
        and resource.kind != DEFAULT_ISSUE_KIND
    ]


async def enrich_issue_entity_relations(
    issue_record: dict[str, typing.Any],
) -> None:
    for entity_guid in issue_record.get("entityGuids", []):
        try:
            entity = await EntitiesHandler().get_entity(entity_guid=entity_guid)
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
    updated_entities: list[dict[str, typing.Any]] = []
    newrelic_types = resource_config.selector.newrelic_types or []

    for entity_guid in entity_guids:
        try:
            entity = await EntitiesHandler().get_entity(entity_guid=entity_guid)
            entity_type = entity["type"]
            if newrelic_types and entity_type not in newrelic_types:
                continue

            if resource_config.selector.calculate_open_issue_count:
                number_of_open_issues = (
                    await IssuesHandler().get_number_of_issues_by_entity_guid(
                        entity_guid,
                        issue_state=IssueState.ACTIVATED,
                    )
                )
                entity["__open_issues_count"] = number_of_open_issues

            updated_entities.append(entity)
        except Exception as err:
            logger.exception(
                "Failed to get entity for issue event, continuing",
                entity_guid=entity_guid,
                err=str(err),
            )

    return updated_entities
