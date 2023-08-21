from typing import Any
from enum import StrEnum
from loguru import logger
from port_ocean.context.ocean import ocean
from argocd_integration.client import ArgocdClient


class ObjectKind(StrEnum):
    PROJECT = "projects"
    APPLICATION = "applications"
    DEPLOYMENT = "deployments"


argocd_client = ArgocdClient(
    ocean.integration_config["token"],
    ocean.integration_config["server_url"],
)


@ocean.on_resync(ObjectKind.PROJECT)
async def on_projects_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing ArgoCD resource: {kind}")
    return await argocd_client.get_argocd_resource(resource_type=ObjectKind.PROJECT)


@ocean.on_resync(ObjectKind.APPLICATION)
async def on_applications_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing ArgoCD resource: {kind}")
    return await argocd_client.get_argocd_resource(resource_type=ObjectKind.APPLICATION)


@ocean.on_resync(ObjectKind.DEPLOYMENT)
async def on_deployments_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing ArgoCD resource: {kind}")
    return await argocd_client.get_argocd_deployments()
