import asyncio
from typing import Any, List
from loguru import logger

from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_RESULT
from utils import ObjectKind, init_terraform_client
from enrich import (
    enrich_state_versions_with_output_data,
    enrich_workspaces_with_tags,
)
from webhook_processors.run_webhook_processor import RunWebhookProcessor
from webhook_processors.workspace_webhook_processor import WorkspaceWebhookProcessor
from webhook_processors.state_version_webhook_processor import (
    StateVersionWebhookProcessor,
)
from webhook_processors.state_file_webhook_processor import StateFileWebhookProcessor
from webhook_processors.webhook_client import TerraformWebhookClient


SKIP_WEBHOOK_CREATION = False


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


@ocean.on_resync(ObjectKind.STATE_FILE)
async def resync_state_files(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    terraform_client = init_terraform_client()

    async for state_files_batch in terraform_client.get_paginated_state_files():
        logger.info(f"Received batch of {len(state_files_batch)} {kind}")
        yield state_files_batch


@ocean.on_resync()
async def on_create_webhook_resync(kind: str) -> RAW_RESULT:
    global SKIP_WEBHOOK_CREATION

    if SKIP_WEBHOOK_CREATION:
        logger.info("Webhook has already been set")
        return []

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return []

    if base_url := ocean.app.base_url:
        logger.warning(f"Creating webhooks for base URL: {base_url}")
        config = ocean.integration_config
        webhook_client = TerraformWebhookClient(
            config["terraform_cloud_host"],
            config["terraform_cloud_token"],
        )
        await webhook_client.ensure_workspace_webhooks(base_url=base_url)

    SKIP_WEBHOOK_CREATION = True
    return []


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Terraform integration")

    if not ocean.app.base_url:
        logger.warning(
            "No base URL configured, skipping webhook creation. "
            "Without setting up the webhook, the integration will not export live changes from Terraform"
        )


# Register webhook processors
ocean.add_webhook_processor("/webhook", RunWebhookProcessor)
ocean.add_webhook_processor("/webhook", WorkspaceWebhookProcessor)
ocean.add_webhook_processor("/webhook", StateVersionWebhookProcessor)
ocean.add_webhook_processor("/webhook", StateFileWebhookProcessor)
