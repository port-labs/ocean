import typing
from typing import Any
import asyncio

from loguru import logger

from clients.pagerduty import PagerDutyClient
from integration import ObjectKind, PagerdutyServiceResourceConfig
from integration import (
    PagerdutyIncidentResourceConfig,
    PagerdutyScheduleResourceConfig,
    PagerdutyOncallResourceConfig,
    PagerdutyEscalationPolicyResourceConfig,
)
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


def initialize_client() -> PagerDutyClient:
    return PagerDutyClient(
        ocean.integration_config["token"],
        ocean.integration_config["api_url"],
        ocean.integration_config.get("app_host"),
    )


async def enrich_service_with_analytics_data(
    client: PagerDutyClient, services: list[dict[str, Any]], months_period: int
) -> list[dict[str, Any]]:
    analytics_data = await asyncio.gather(
        *[
            client.get_service_analytics(service["id"], months_period)
            for service in services
        ]
    )

    enriched_services = [
        {**service, "__analytics": analytics}
        for service, analytics in zip(services, analytics_data)
    ]

    return enriched_services


async def enrich_incidents_with_analytics_data(
    client: PagerDutyClient,
    incidents: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    analytics_data = await asyncio.gather(
        *[client.get_incident_analytics(incident["id"]) for incident in incidents]
    )

    enriched_incidents = [
        {**incident, "__analytics": analytics}
        for incident, analytics in zip(incidents, analytics_data)
    ]

    return enriched_incidents


@ocean.on_resync(ObjectKind.INCIDENTS)
async def on_incidents_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()

    selector = typing.cast(
        PagerdutyIncidentResourceConfig, event.resource_config
    ).selector

    query_params = selector.api_query_params

    async for incidents in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.INCIDENTS,
        params=query_params.generate_request_params() if query_params else None,
    ):
        logger.info(f"Received batch with {len(incidents)} incidents")

        if selector.incident_analytics:
            enriched_incident_batch = await enrich_incidents_with_analytics_data(
                pager_duty_client, incidents
            )
            yield enriched_incident_batch
        else:
            yield incidents


@ocean.on_resync(ObjectKind.SERVICES)
async def on_services_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()

    selector = typing.cast(
        PagerdutyServiceResourceConfig, event.resource_config
    ).selector

    async for services in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.SERVICES,
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


@ocean.on_resync(ObjectKind.SCHEDULES)
async def on_schedules_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()
    query_params = typing.cast(
        PagerdutyScheduleResourceConfig, event.resource_config
    ).selector.api_query_params

    async for schedules in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.SCHEDULES,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield await pager_duty_client.transform_user_ids_to_emails(schedules)


@ocean.on_resync(ObjectKind.ONCALLS)
async def on_oncalls_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing Pagerduty resource: {kind}")
    pager_duty_client = initialize_client()

    query_params = typing.cast(
        PagerdutyOncallResourceConfig, event.resource_config
    ).selector.api_query_params

    async for oncalls in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.ONCALLS,
        params=query_params.generate_request_params() if query_params else None,
    ):
        yield oncalls


@ocean.on_resync(ObjectKind.ESCALATION_POLICIES)
async def on_escalation_policies_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    pager_duty_client = initialize_client()

    selector = typing.cast(
        PagerdutyEscalationPolicyResourceConfig, event.resource_config
    ).selector

    async for escalation_policies in pager_duty_client.paginate_request_to_pager_duty(
        data_key=ObjectKind.ESCALATION_POLICIES,
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


@ocean.router.post("/webhook")
async def upsert_incident_webhook_handler(data: dict[str, Any]) -> None:
    pager_duty_client = initialize_client()
    event_type = data["event"]["event_type"]
    logger.info(f"Processing Pagerduty webhook for event type: {event_type}")

    if event_type in pager_duty_client.service_delete_events:
        await ocean.unregister_raw(ObjectKind.SERVICES, [data["event"]["data"]])

    elif event_type in pager_duty_client.incident_upsert_events:
        incident_id = data["event"]["data"]["id"]

        incident = await pager_duty_client.get_singular_from_pager_duty(
            object_type=ObjectKind.INCIDENTS, identifier=incident_id
        )

        enriched_incident = await enrich_incidents_with_analytics_data(
            pager_duty_client, [incident["incident"]]
        )
        await ocean.register_raw(ObjectKind.INCIDENTS, enriched_incident)

    elif event_type in pager_duty_client.service_upsert_events:
        service_id = data["event"]["data"]["id"]
        response = await pager_duty_client.get_singular_from_pager_duty(
            object_type=ObjectKind.SERVICES, identifier=service_id
        )
        services = await pager_duty_client.update_oncall_users([response["service"]])

        await ocean.register_raw(ObjectKind.SERVICES, services)


@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    pager_duty_client = initialize_client()
    logger.info("Subscribing to Pagerduty webhooks")
    await pager_duty_client.create_webhooks_if_not_exists()
