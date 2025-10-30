from typing import Optional
from loguru import logger

from harbor.client import HarborClient
from harbor.utils.constants import HarborKind


async def create_or_update_webhook_policy(
    client: HarborClient,
    project_name: str,
    webhook_url: str,
) -> None:
    """
    Create or update Harbor webhook policy for a project

    Args:
        client: Harbor API client
        project_name: Project to configure webhooks for
        webhook_endpoint_url: URL where webhooks should be sent
    """
    try:
        existing_webhooks = await client._send_api_request(
            "GET",
            f"/projects/{project_name}/webhook/policies"
        )

        webhook_config = {
            "name": "Port Ocean Integration",
            "description": "Real-time sync to Port",
            "enabled": True,
            "event_types": [
                "PUSH_ARTIFACT",
                "DELETE_ARTIFACT",
                "SCANNING_COMPLETED",
                "SCANNING_FAILED",
            ],
            "targets": [{
                "type": "http",
                "address": webhook_url,
                "skip_cert_verify": True,
            }]
        }

        _webhook = next(
            (w for w in existing_webhooks if w.get("name") == "Port Ocean Integration"),
            None
        )

        if _webhook:
            webhook_id = _webhook["id"]
            logger.info(f"harbor_ocean::webhooks::Updating existing webhook policy {webhook_id} for project {project_name}")
            await client._send_api_request(
                "PUT",
                f"/projects/{project_name}/webhook/policies/{webhook_id}",
                json_data=webhook_config
            )
        else:
            logger.info(f"harbor_ocean::webhooks::Creating new webhook policy for project {project_name}")
            await client._send_api_request(
                "POST",
                f"/projects/{project_name}/webhook/policies",
                json_data=webhook_config
            )

        logger.info(f"harbor_ocean::webhooks::Webhook policy configured for project {project_name}")

    except Exception as e:
        logger.error(f"harbor_ocean::webhooks::Failed to configure webhook for project {project_name}: {e}")


async def setup_webhooks_for_all_projects(
    client: HarborClient,
    webhook_url: str
) -> None:
    """
    Configure webhooks for all projects in Harbor

    Args:
        client: Harbor API client
        webhook_url: URL where webhooks should be sent
    """
    logger.info("harbor_oceean::webhooks::Setting up Harbor webhook policies...")

    try:
        projects = []
        async for batch in client.get_paginated_resources(HarborKind.PROJECT):
            projects.extend(batch)

        logger.info(f"Configuring webhooks for {len(projects)} projects")

        for project in projects:
            project_name = project.get("name")
            if project_name:
                await create_or_update_webhook_policy(
                    client,
                    project_name,
                    webhook_url
                )

        logger.info("harbor_ocean::webhooks::Webhook policies configured successfully")

    except Exception as e:
        logger.error(f"harbor_ocean::webhooks::Error during webhook setup: {e}")
