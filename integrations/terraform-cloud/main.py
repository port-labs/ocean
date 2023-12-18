from enum import StrEnum
from typing import Any
from client import TerraformClient
from port_ocean.context.ocean import ocean
from loguru import logger
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


class ObjectKind(StrEnum):
    WORKSPACE = "workspace"
    RUN = "run"


def init_terraform_client() -> TerraformClient:
    """
    Intialize Terraform Client
    """
    config = ocean.integration_config
    
    terraform_client = TerraformClient(
                    config["terraform_host"],
                    config["terraform_token"],
                    config["terraform_organization"],
                    )

    return terraform_client


async def setup_application()->Any:
        
    app_host = ocean.integration_config.get("app_host")

    if not app_host:
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Terraform"
        )
        return

    terraform_client = init_terraform_client()
    await terraform_client.create_workspace_webhook(app_host=app_host)



@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    terraform_client = init_terraform_client()

    run_id = data["run_id"]
    logger.info(f"Processing Terraform run event for run : {run_id}")

    run = await terraform_client.get_single_run(run_id)
    await ocean.register_raw(ObjectKind.RUN, [run])

    workspace_id = data['workspace_id']
    logger.info(f"Processing Terraform run event for workspace : {workspace_id}")

    workspace = await terraform_client.get_single_workspace(workspace_id)
    await ocean.register_raw(ObjectKind.WORKSPACE, [workspace])

    logger.info("Terraform webhook event processed")
    return {"ok": True}



@ocean.on_resync(ObjectKind.WORKSPACE)
async def resync_workspaces(kind: str) -> list[dict[Any, Any]]:
    terraform_client = init_terraform_client()

    async for workspace in terraform_client.get_paginated_workspaces():
        logger.info(f"Received {len(workspace)} batch workspaces")
        yield workspace



@ocean.on_resync(ObjectKind.RUN)
async def resync_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()

    async for workspaces in terraform_client.get_paginated_workspaces():
        logger.info(f"Received {len(workspaces)} batch runs")
        for workspace in workspaces:
            async for runs in terraform_client.get_paginated_runs_for_workspace(workspace['id']):
                yield runs


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Terraform integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()
