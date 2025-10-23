from typing import Any
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from jfrog.client import JFrogClient


def init_client() -> JFrogClient:
    """Initialize JFrog client from integration config"""
    return JFrogClient(
        jfrog_host_url=ocean.integration_config["jfrog_host_url"],
        access_token=ocean.integration_config["access_token"],
        include_vulnerabilities=ocean.integration_config.get("include_vulnerabilities", True),
        repository_types=ocean.integration_config.get("repository_types"),
    )


@ocean.on_resync("repository")
async def on_repository_resync(kind: str) -> list[dict[str, Any]]:
    """Sync JFrog repositories"""
    client = init_client()
    return await client.get_repositories()


@ocean.on_resync("build")
async def on_build_resync(kind: str) -> list[dict[str, Any]]:
    """Sync JFrog builds"""
    client = init_client()
    return await client.get_builds()


@ocean.on_resync("project")
async def on_project_resync(kind: str) -> list[dict[str, Any]]:
    """Sync JFrog projects with roles"""
    client = init_client()
    projects = await client.get_projects()

    # Enrich projects with roles
    for project in projects:
        project_key = project.get("project_key")
        if project_key:
            project["roles"] = await client.get_project_roles(project_key)

    return projects


@ocean.on_resync("dockerImage")
async def on_docker_image_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Docker images"""
    client = init_client()
    async for images in client.get_docker_images():
        logger.info(f"Received batch with {len(images)} Docker images")
        yield images


@ocean.on_resync("vulnerability")
async def on_vulnerability_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync vulnerabilities for Docker images"""
    client = init_client()

    async for images in client.get_docker_images():
        vulnerabilities = []
        for image in images:
            vulns = await client.get_vulnerabilities(image)
            # Add image reference to each vulnerability
            for vuln in vulns:
                vuln["__image"] = image["fullName"]
            vulnerabilities.extend(vulns)

        if vulnerabilities:
            logger.info(f"Found {len(vulnerabilities)} vulnerabilities")
            yield vulnerabilities
