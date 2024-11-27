from asyncio import gather
import asyncio
from enum import StrEnum
from typing import Any, List
from loguru import logger

from client import TerraformClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_RESULT


class ObjectKind(StrEnum):
    WORKSPACE = "workspace"
    RUN = "run"
    STATE_VERSION = "state-version"
    PROJECT = "project"
    ORGANIZATION = "organization"


SKIP_WEBHOOK_CREATION = False


def init_terraform_client() -> TerraformClient:
    """
    Intialize Terraform Client
    """
    config = ocean.integration_config

    terraform_client = TerraformClient(
        config["terraform_cloud_host"],
        config["terraform_cloud_token"],
    )

    return terraform_client


## Enriches the state version with output
async def enrich_state_versions_with_output_data(
    http_client: TerraformClient, state_versions: List[dict[str, Any]]
) -> list[dict[str, Any]]:
    async def fetch_output(state_version: dict[str, Any]) -> dict[str, Any]:
        try:
            output = await http_client.get_state_version_output(state_version["id"])
            return {**state_version, "__output": output}
        except Exception as e:
            logger.warning(
                f"Failed to fetch output for state version {state_version['id']}: {e}"
            )
            return {**state_version, "__output": {}}

    enriched_versions = await gather(
        *[fetch_output(state_version) for state_version in state_versions]
    )
    return list(enriched_versions)


async def enrich_workspaces_with_tags(
    http_client: TerraformClient, workspaces: List[dict[str, Any]]
) -> list[dict[str, Any]]:
    async def get_tags_for_workspace(workspace: dict[str, Any]) -> dict[str, Any]:
        try:
            tags = []
            async for tag_batch in http_client.get_workspace_tags(workspace["id"]):
                tags.extend(tag_batch)
            return {**workspace, "__tags": tags}
        except Exception as e:
            logger.warning(f"Failed to fetch tags for workspace {workspace['id']}: {e}")
            return {**workspace, "__tags": []}

    enriched_workspaces = await gather(
        *[get_tags_for_workspace(workspace) for workspace in workspaces]
    )
    return list(enriched_workspaces)


async def enrich_workspace_with_tags(
    http_client: TerraformClient, workspace: dict[str, Any]
) -> dict[str, Any]:
    try:
        tags = []
        async for tag_batch in http_client.get_workspace_tags(workspace["id"]):
            tags.extend(tag_batch)
        return {**workspace, "__tags": tags}
    except Exception as e:
        logger.warning(f"Failed to fetch tags for workspace {workspace['id']}: {e}")
        return {**workspace, "__tags": []}


@ocean.on_resync(ObjectKind.ORGANIZATION)
async def resync_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()
    async for organizations in terraform_client.get_paginated_organizations():
        logger.info(f"Received {len(organizations)} batch {kind}s")
        yield organizations


@ocean.on_resync(ObjectKind.PROJECT)
async def resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()
    async for projects in terraform_client.get_paginated_projects():
        logger.info(f"Received {len(projects)} batch {kind}s")
        yield projects


@ocean.on_resync(ObjectKind.WORKSPACE)
async def resync_workspaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()
    async for workspaces in terraform_client.get_paginated_workspaces():
        logger.info(f"Received {len(workspaces)} batch {kind}s")
        enriched_workspace_batch = await enrich_workspaces_with_tags(
            terraform_client, workspaces
        )
        yield enriched_workspace_batch


@ocean.on_resync(ObjectKind.RUN)
async def resync_runs(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()
    BATCH_SIZE = 25  # Stay safely under 30 req/sec limit

    async def process_workspace(workspace: dict[str, Any]) -> List[dict[str, Any]]:
        runs = []
        async for run_batch in terraform_client.get_paginated_runs_for_workspace(
            workspace["id"]
        ):
            if run_batch:
                runs.extend(run_batch)
        return runs

    async for workspaces in terraform_client.get_paginated_workspaces():
        logger.info(f"Processing batch of {len(workspaces)} workspaces")

        # Process in batches to stay under rate limit
        for i in range(0, len(workspaces), BATCH_SIZE):
            batch = workspaces[i : i + BATCH_SIZE]
            tasks = [process_workspace(workspace) for workspace in batch]

            for completed_task in asyncio.as_completed(tasks):
                runs = await completed_task
                if runs:
                    yield runs


@ocean.on_resync(ObjectKind.STATE_VERSION)
async def resync_state_versions(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()

    async for state_versions_batch in terraform_client.get_paginated_state_versions():
        logger.info(f"Received batch with {len(state_versions_batch)} {kind}")

        enriched_state_versions_batch = await enrich_state_versions_with_output_data(
            terraform_client, state_versions_batch
        )
        yield enriched_state_versions_batch


@ocean.on_resync()
async def on_create_webhook_resync(kind: str) -> RAW_RESULT:
    global SKIP_WEBHOOK_CREATION

    if SKIP_WEBHOOK_CREATION:
        logger.info("Webhook has already been set")
        return []

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return []

    terraform_client = init_terraform_client()
    if app_host := ocean.integration_config.get("app_host"):
        await terraform_client.create_workspace_webhook(app_host=app_host)

    SKIP_WEBHOOK_CREATION = True
    return []


@ocean.router.post("/webhook")
async def handle_webhook_request(data: dict[str, Any]) -> dict[str, Any]:
    for notifications in data["notifications"]:
        if notifications["trigger"] == "verification":
            logger.info("Webhook verification challenge accepted")
            return {"ok": True}

    terraform_client = init_terraform_client()

    run_id = data["run_id"]
    logger.info(f"Processing Terraform run event for run: {run_id}")

    workspace_id = data["workspace_id"]
    logger.info(f"Processing Terraform run event for workspace: {workspace_id}")

    run, workspace = await gather(
        terraform_client.get_single_run(run_id),
        terraform_client.get_single_workspace(workspace_id),
    )

    enriched_workspace = await enrich_workspace_with_tags(terraform_client, workspace)

    await gather(
        ocean.register_raw(ObjectKind.RUN, [run]),
        ocean.register_raw(ObjectKind.WORKSPACE, [enriched_workspace]),
    )

    logger.info("Terraform webhook event processed")
    return {"ok": True}


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Terraform integration")

    if not ocean.integration_config.get("app_host"):
        logger.warning(
            "No app host provided, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Terraform"
        )
