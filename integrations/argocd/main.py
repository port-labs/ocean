from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from argocd_integration.client import ArgocdClient
from argocd_integration.utils import ObjectKind
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
    return await argocd_client.get_resources(resource_kind=ObjectKind(kind))


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
