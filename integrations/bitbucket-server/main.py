from typing import Any, cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean

from .client import BitbucketClient
from .integration import BitbucketResourceConfig, ObjectKind


def initialize_client() -> BitbucketClient:
    return BitbucketClient(
        username=ocean.integration_config["username"],
        password=ocean.integration_config["password"],
        base_url=ocean.integration_config["base_url"],
    )


@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> list[dict[Any, Any]]:
    selector = cast(BitbucketResourceConfig, event.resource_config).selector
    logger.info(f"Resyncing projects with filter: {selector.projects_filter}")
    client = initialize_client()
    projects = await client.get_projects(projects_filter=selector.projects_filter)
    logger.info(f"Received {len(projects)} projects")
    return projects


@ocean.on_resync(ObjectKind.REPOSITORY)
async def on_resync_repositories(kind: str) -> list[dict[Any, Any]]:
    selector = cast(BitbucketResourceConfig, event.resource_config).selector
    logger.info(f"Resyncing repositories for projects: {selector.projects_filter}")
    client = initialize_client()

    all_repositories = []
    projects = await client.get_projects(projects_filter=selector.projects_filter)

    for project in projects:
        repositories = await client.get_repositories(project["key"])
        for repo in repositories:
            repo["project"] = project
            readme = await client.get_repository_readme(project["key"], repo["slug"])
            latest_commit = await client.get_latest_commit(project["key"], repo["slug"])
            repo["readme"] = readme
            repo["latest_commit"] = latest_commit
        all_repositories.extend(repositories)

    logger.info(f"Received {len(all_repositories)} repositories")
    return all_repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def on_resync_pull_requests(kind: str) -> list[dict[Any, Any]]:
    selector = cast(BitbucketResourceConfig, event.resource_config).selector
    logger.info(f"Resyncing pull requests with state: {selector.pull_request_state}")
    client = initialize_client()

    all_pull_requests = []
    projects = await client.get_projects(projects_filter=selector.projects_filter)

    for project in projects:
        repositories = await client.get_repositories(project["key"])
        for repo in repositories:
            pull_requests = await client.get_pull_requests(
                project["key"],
                repo["slug"],
                state=selector.pull_request_state,
            )
            for pr in pull_requests:
                pr["project"] = project
                pr["repository"] = repo
            all_pull_requests.extend(pull_requests)

    logger.info(f"Received {len(all_pull_requests)} pull requests")
    return all_pull_requests


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> list[dict[Any, Any]]:
    logger.info("Resyncing users")
    client = initialize_client()
    users = await client.get_users()
    logger.info(f"Received {len(users)} users")
    return users


@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Bitbucket Server integration")
    client = initialize_client()

    # Test connection to Bitbucket Server
    try:
        await client.get_projects()
        logger.info("Successfully connected to Bitbucket Server")
    except Exception as e:
        logger.error(f"Failed to connect to Bitbucket Server: {e}")
        raise Exception("Failed to connect to Bitbucket Server")
