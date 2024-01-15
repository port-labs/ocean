from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from client import ArgocdClient, ObjectKind
from fastapi import Request


def init_client() -> ArgocdClient:
    return ArgocdClient(
        ocean.integration_config["token"],
        ocean.integration_config["server_url"],
    )


@ocean.on_resync()
async def on_resources_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info(f"Listing ArgoCD resource: {kind}")
    argocd_client = init_client()

    try:
        if kind == ObjectKind.HISTORY:
            return []
        else:
            return await argocd_client.get_resources(resource_kind=ObjectKind(kind))
    except ValueError:
        logger.error(f"Invalid resource kind: {kind}")
        raise


@ocean.on_resync(kind=ObjectKind.HISTORY)
async def on_history_resync(kind: str) -> list[dict[Any, Any]]:
    logger.info("Listing ArgoCD deployment history")
    argocd_client = init_client()

    try:
        return await argocd_client.get_deployment_history()
    except Exception:
        logger.error("Failed to fetch ArgoCD deployment history")
        raise


@ocean.router.post("/webhook")
async def on_application_event_webhook_handler(request: Request) -> None:
    data = await request.json()
    logger.debug(f"received webhook event data: {data}")
    argocd_client = init_client()

    if data["action"] == "upsert":
        application = await argocd_client.get_application_by_name(
            data["application_name"]
        )
        await ocean.register_raw(ObjectKind.APPLICATION, [application])
