from typing import cast
from loguru import logger
from port_ocean.context.event import event
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from integration import ApplicationResourceConfig, ManagedResourceResourceConfig
from misc import ResourceKindsWithSpecialHandling, ObjectKind, init_client
from port_ocean.context.ocean import ocean
from webhooks.webhook_processor.application_webhook_processor import (
    ArgocdApplicationWebhookProcessor,
)


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in ResourceKindsWithSpecialHandling:
        logger.info(f"Kind {kind} has a special handling. Skipping...")
        yield []
    else:
        argocd_client = init_client()
        async for cluster in argocd_client.get_resources(
            resource_kind=ObjectKind(kind)
        ):
            yield cluster


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.APPLICATION)
async def on_applications_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    argocd_client = init_client()
    selector = cast(ApplicationResourceConfig, event.resource_config).selector
    params = (
        selector.query_params.generate_request_params if selector.query_params else None
    )
    async for application in argocd_client.get_resources(
        resource_kind=ResourceKindsWithSpecialHandling.APPLICATION, query_params=params
    ):
        yield application


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.CLUSTER)
async def on_clusters_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    argocd_client = init_client()
    async for cluster in argocd_client.get_clusters():
        yield cluster


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.DEPLOYMENT_HISTORY)
async def on_history_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    argocd_client = init_client()
    async for history in argocd_client.get_deployment_history():
        yield history


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.KUBERNETES_RESOURCE)
async def on_managed_k8s_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    argocd_client = init_client()
    async for resources in argocd_client.get_kubernetes_resource():
        yield resources


@ocean.on_resync(kind=ResourceKindsWithSpecialHandling.MANAGED_RESOURCE)
async def on_managed_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    argocd_client = init_client()

    selector = cast(ManagedResourceResourceConfig, event.resource_config).selector
    app_filters = selector.app_filters
    params = app_filters.generate_request_params if app_filters else None
    async for app_batch in argocd_client.get_resources(
        resource_kind=ResourceKindsWithSpecialHandling.APPLICATION, query_params=params
    ):
        if not app_batch:
            logger.info(
                "No applications were found. Skipping managed resources ingestion"
            )
            continue

        for application in app_batch:
            if application:
                async for managed_resources in argocd_client.get_managed_resources(
                    application=application
                ):
                    logger.info(
                        f"Ingesting managed resources for application: {application.get('metadata', {}).get('name')}"
                    )
                    yield managed_resources


ocean.add_webhook_processor("/webhook", ArgocdApplicationWebhookProcessor)
