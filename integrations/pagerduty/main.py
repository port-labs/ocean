import typing
from typing import Any

from loguru import logger
from webhook_processors.incidents import IncidentWebhookProcessor
from webhook_processors.services import ServiceWebhookProcessor
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from clients.pagerduty import PagerDutyClient
from integration import (
    OBJECTS_WITH_SPECIAL_HANDLING,
    PagerdutyEscalationPolicyResourceConfig,
    PagerdutyIncidentResourceConfig,
    PagerdutyOncallResourceConfig,
    PagerdutyScheduleResourceConfig,
    PagerdutyServiceResourceConfig,
)
from kinds import Kinds


async def enrich_service_with_analytics_data(
    client: PagerDutyClient, services: list[dict[str, Any]], months_period: int
) -> list[dict[str, Any]]:
    async def fetch_service_analytics(
        services: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        service_ids = [service["id"] for service in services]
        try:
            services_analytics = await client.get_service_analytics(
                service_ids, months_period
            )
            # Map analytics to corresponding services
            service_analytics_map = {
                analytics["service_id"]: analytics for analytics in services_analytics
            }
            enriched_services = [
                {
                    **service,
                    "__analytics": service_analytics_map.get(service["id"], None),
                }
                for service in services
            ]
            return enriched_services
        except Exception as e:
            logger.error(f"Failed to fetch analytics for service {service_ids}: {e}")
            return [{**service, "__analytics": None} for service in services]

    return await fetch_service_analytics(services)


@ocean.on_resync(Kinds.INCIDENTS)
async def on_incidents_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = PagerDutyClient.from_ocean_configuration()

    selector = typing.cast(
        PagerdutyIncidentResourceConfig, event.resource_config
    ).selector

    query_params = selector.api_query_params

    async for incidents in pager_duty_client.paginate_request_to_pager_duty(
        resource=Kinds.INCIDENTS,
        params=query_params.generate_request_params() if query_params else None,
    ):
        logger.info(f"Received batch with {len(incidents)} incidents")

        if selector.incident_analytics:
            yield (
                await pager_duty_client.enrich_incidents_with_analytics_data(incidents)
            )
        else:
            yield incidents


@ocean.on_resync(Kinds.SERVICES)
async def on_services_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = PagerDutyClient.from_ocean_configuration()

    selector = typing.cast(
        PagerdutyServiceResourceConfig, event.resource_config
    ).selector

    async for services in pager_duty_client.paginate_request_to_pager_duty(
        resource=Kinds.SERVICES,
        params=(
            selector.api_query_params.generate_request_params()
            if selector.api_query_params
            else None
        ),
    ):
        logger.info(f"Received batch with {len(services)} services")

        if selector.service_analytics:
            services = await enrich_service_with_analytics_data(
                pager_duty_client, services, selector.analytics_months_period
            )

        yield await pager_duty_client.update_oncall_users(services)


@ocean.on_resync(Kinds.SCHEDULES)
async def on_schedules_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = PagerDutyClient.from_ocean_configuration()
    query_params = typing.cast(
        PagerdutyScheduleResourceConfig, event.resource_config
    ).selector.api_query_params

    async for schedules in pager_duty_client.paginate_request_to_pager_duty(
        resource=Kinds.SCHEDULES,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield await pager_duty_client.transform_user_ids_to_emails(schedules)


@ocean.on_resync(Kinds.ONCALLS)
async def on_oncalls_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = PagerDutyClient.from_ocean_configuration()

    query_params = typing.cast(
        PagerdutyOncallResourceConfig, event.resource_config
    ).selector.api_query_params

    async for oncalls in pager_duty_client.paginate_request_to_pager_duty(
        resource=Kinds.ONCALLS,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield oncalls


@ocean.on_resync(Kinds.ESCALATION_POLICIES)
async def on_escalation_policies_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    pager_duty_client = PagerDutyClient.from_ocean_configuration()

    selector = typing.cast(
        PagerdutyEscalationPolicyResourceConfig, event.resource_config
    ).selector

    async for escalation_policies in pager_duty_client.paginate_request_to_pager_duty(
        resource=Kinds.ESCALATION_POLICIES,
        params=(
            selector.api_query_params.generate_request_params()
            if selector.api_query_params
            else None
        ),
    ):
        if selector.attach_oncall_users:
            logger.info("Fetching oncall users for escalation policies")
            oncall_users = await pager_duty_client.get_oncall_user(
                *[policy["id"] for policy in escalation_policies]
            )

            for policy in escalation_policies:
                policy["__oncall_users"] = [
                    user
                    for user in oncall_users
                    if user["escalation_policy"]["id"] == policy["id"]
                ]
            yield escalation_policies
        else:
            yield escalation_policies


@ocean.on_resync()
async def on_global_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:

    if kind in OBJECTS_WITH_SPECIAL_HANDLING:
        logger.info(f"Kind {kind} has a special handling. Skipping...")
        return
    else:
        pager_duty_client = PagerDutyClient.from_ocean_configuration()

        try:
            async for (
                resource_batch
            ) in pager_duty_client.paginate_request_to_pager_duty(resource=kind):
                logger.info(f"Received batch with {len(resource_batch)} {kind}")
                yield resource_batch
        except Exception as e:
            logger.error(
                f"Failed to fetch {kind} from Pagerduty due to error: {e}. For information on supported resources, please refer to our documentation at https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/incident-management/pagerduty/#supported-resources"
            )
            raise e


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    pager_duty_client = PagerDutyClient.from_ocean_configuration()
    logger.info("Subscribing to Pagerduty webhooks")
    await pager_duty_client.create_webhooks_if_not_exists()


ocean.add_webhook_processor("/webhook", ServiceWebhookProcessor)
ocean.add_webhook_processor("/webhook", IncidentWebhookProcessor)
