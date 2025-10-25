from typing import Any
from datetime import datetime
from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE
from jfrog.client import JFrogClient


def init_client() -> JFrogClient:
    """Initialize JFrog client from integration config"""
    return JFrogClient(
        jfrog_host_url=ocean.integration_config["jfrog_host_url"],
        access_token=ocean.integration_config["access_token"],
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
    async for project in projects:
        project_key = project.get("project_key")
        if project_key:
            project["roles"] = await client.get_project_roles(project_key)

    return projects


@ocean.on_resync("dockerImage")
async def on_docker_image_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync Docker images with enriched metadata"""
    client = init_client()
    async for images in client.get_docker_images():
        # Enrich images with vulnerability counts
        for image in images:
            vulns = await client.get_vulnerabilities(image)

            # Calculate vulnerability counts by severity
            vuln_counts = {
                "Critical": 0,
                "High": 0,
                "Medium": 0,
                "Low": 0,
            }

            for vuln in vulns:
                severity = vuln.get("severity", "Unknown")
                if severity in vuln_counts:
                    vuln_counts[severity] += 1

            # Add counts to image data
            image["vulnerabilityCount"] = len(vulns)
            image["criticalVulns"] = vuln_counts["Critical"]
            image["highVulns"] = vuln_counts["High"]
            image["mediumVulns"] = vuln_counts["Medium"]
            image["lowVulns"] = vuln_counts["Low"]

            # Add last scanned timestamp
            image["lastScanned"] = datetime.utcnow().isoformat() + "Z"

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


@ocean.on_resync("baseImageVulnerability")
async def on_base_image_vulnerability_resync(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync base image vulnerabilities for Docker images"""
    client = init_client()

    async for images in client.get_docker_images():
        base_vulnerabilities = []
        for image in images:
            base_vulns = await client.get_base_image_vulnerabilities(image)
            # Add image reference to each vulnerability
            for vuln in base_vulns:
                vuln["__image"] = image["fullName"]
            base_vulnerabilities.extend(base_vulns)

        if base_vulnerabilities:
            logger.info(f"Found {len(base_vulnerabilities)} base image vulnerabilities")
            yield base_vulnerabilities
