from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from argocd_integration.client import ArgocdClient
from argocd_integration.utils import ObjectKind


def init_client() -> ArgocdClient:

    return ArgocdClient(
        ocean.integration_config["token"],
        ocean.integration_config["server_url"],
    )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing ArgoCD resource: {kind}")
    argocd_client = init_client()
    return await argocd_client.get_all_projects()


@ocean.on_resync(ObjectKind.APPLICATION)
async def on_applications_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    logger.info(f"Listing ArgoCD resource: {kind}")
    argocd_client = init_client()
    async for applications in argocd_client.get_all_applications():
        logger.debug(f"Received batch with {len(applications)} applications")
        yield applications


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def on_deployments_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing ArgoCD resource: {kind}")
    argocd_client = init_client()
    return await argocd_client.get_all_deployments()


@ocean.router.post("/webhook")
async def on_application_event_webhook_handler(data: dict[str, Any]) -> None:
    argocd_client = init_client()

    if data["action"] == "upsert":
        application = await argocd_client.get_application_by_name(data["application_name"])
        deployment = argocd_client.get_deployment_by_application(application)
        ocean.register_raw(ObjectKind.APPLICATION, [application])
        ocean.register_raw(ObjectKind.DEPLOYMENT, deployment)
    
    elif data["action"] == "delete":
        application = await argocd_client.get_application_by_name(data["application_name"])
        ocean.unregister_raw(ObjectKind.APPLICATION, [application])


