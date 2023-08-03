import httpx
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from newrelic_integration.core.entities import EntitiesHandler
from newrelic_integration.core.issues import IssuesHandler, IssueState, IssueEvent
from newrelic_integration.utils import (
    get_port_resource_configuration_by_newrelic_entity_type,
    get_port_resource_configuration_by_port_kind,
)


@ocean.on_resync()
async def resync_entities(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        port_resource_configuration = (
            await get_port_resource_configuration_by_port_kind(kind)
        )
        # mainly for issues newRelicAlert as it has different resync logic than entities
        if not port_resource_configuration.get("selector", {}).get(
            "entity_query_filter"
        ):
            logger.debug(
                "Skipping resync for kind without entity_query_filter",
                kind=kind,
            )
            return
        else:
            async with httpx.AsyncClient() as http_client:
                async for entity in EntitiesHandler.list_entities_by_resource_kind(
                    http_client, kind
                ):
                    if port_resource_configuration.get("selector", {}).get(
                        "calculate_open_issue_count"
                    ):
                        number_of_open_issues = (
                            await IssuesHandler.get_number_of_issues_by_entity_guid(
                                http_client,
                                entity["guid"],
                                issue_state=IssueState.ACTIVATED,
                            )
                        )
                        entity["open_issues_count"] = number_of_open_issues
                    yield entity


@ocean.on_resync(kind="newRelicAlert")
async def resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    with logger.contextualize(resource_kind=kind):
        async with httpx.AsyncClient() as http_client:
            issues = await IssuesHandler.list_issues(http_client)
            for issue in issues:
                yield issue


@ocean.router.post("/events")
async def handle_issues_events(issue: IssueEvent) -> dict[str, bool]:
    with logger.contextualize(issue_id=issue.id, issue_state=issue.state):
        logger.info(
            "Received issue event",
        )
        issue_record = issue.dict(by_alias=True)
        async with httpx.AsyncClient() as http_client:
            for entity_guid in issue_record["entityGuids"]:
                # get the entity from new
                entity = await EntitiesHandler.get_entity(
                    http_client, entity_guid=entity_guid
                )
                resource_configuration = (
                    await get_port_resource_configuration_by_newrelic_entity_type(
                        entity["type"]
                    )
                )
                if not resource_configuration:
                    logger.warning(
                        "Received issue event for unknown entity type, ignoring",
                        entity_type=entity["type"],
                    )
                else:
                    if resource_configuration.get("selector", {}).get(
                        "calculate_open_issue_count"
                    ):
                        number_of_open_issues = (
                            await IssuesHandler().get_number_of_issues_by_entity_guid(
                                http_client,
                                entity_guid,
                                issue_state=IssueState.ACTIVATED,
                            )
                        )
                        entity["open_issues_count"] = number_of_open_issues
                    issue_record.setdefault(
                        entity["type"],
                        {},
                    ).setdefault(
                        "entity_guids", []
                    ).append(entity_guid)
                    await ocean.register_raw(resource_configuration["kind"], [entity])
        issue_resource_config = (
            await get_port_resource_configuration_by_newrelic_entity_type("ISSUE")
        )
        # get the port issue kind from the resource configuration if exists, otherwise use the default kind newRelicAlert
        port_issue_kind = issue_resource_config.get("kind", "newRelicAlert")
        await ocean.register_raw(port_issue_kind, [issue_record])
        return {"ok": True}
