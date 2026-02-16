from fastapi import Request
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import ArgocdClient, ObjectKind, ResourceKindsWithSpecialHandling
from port_ocean.context.ocean import ocean


def init_client() -> ArgocdClient:
    return ArgocdClient(
        ocean.integration_config["token"],
        ocean.integration_config["server_url"],
        ocean.integration_config["ignore_server_error"],
        ocean.integration_config["allow_insecure"],
        ocean.integration_config["custom_http_headers"],
        ocean.config.streaming.enabled,
    )


@ocean.on_resync()
async def on_resources_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind in ResourceKindsWithSpecialHandling:
        logger.info(f"Kind {kind} has a special handling. Skipping...")
        yield []
    else:
        argocd_client = init_client()
        async for cluster in argocd_client.get_resources_for_available_clusters(
            resource_kind=ObjectKind(kind)
        ):
            yield cluster


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

    applications_list = []
    async for app_batch in argocd_client.get_resources_for_available_clusters(
        resource_kind=ObjectKind.APPLICATION
    ):
        applications_list.extend(app_batch)
    applications = applications_list
    if not applications:
        logger.info("No applications were found. Skipping managed resources ingestion")
        return

    for application in applications:
        if application:
            async for managed_resources in argocd_client.get_managed_resources(
                application=application
            ):
                logger.info(
                    f"Ingesting managed resources for application: {application.get('metadata', {}).get('name')}"
                )
                yield managed_resources


@ocean.router.post("/webhook")
async def on_application_event_webhook_handler(request: Request) -> None:
    data = await request.json()
    logger.debug(f"received webhook event data: {data}")
    argocd_client = init_client()

    if data["action"] == "upsert":
        application = await argocd_client.get_application_by_name(
            data["application_name"],
            namespace=data.get("application_namespace"),
        )
        await ocean.register_raw(ObjectKind.APPLICATION, [application])
