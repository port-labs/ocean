from typing import Any

from clients.bitbucket import BitbucketClient
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE


def init_bitbucket_client() -> BitbucketClient:
    username = ocean.integration_config["bitbucket_username"]
    password = ocean.integration_config["bitbucket_app_password"]
    workspace = ocean.integration_config["bitbucket_workspace"]
    return BitbucketClient(username, password, workspace)


# Required
# Listen to the resync event of all the kinds specified in the mapping inside port.
# Called each time with a different kind that should be returned from the source system.
@ocean.on_resync()
async def on_resync(kind: str) -> list[dict[Any, Any]]:
    # get all projects
    if kind == "project":
        return [
            {
                "uuid": f"project-{x}",
                "name": f"project-{x}",
                "url": f"https://bitbucket.org/project-{x}",
            }
            for x in range(5)
        ]

    # get all repositories
    if kind == "repository":
        return [
            {
                "uuid": f"repository-{x}",
                "name": f"repository-{x}",
                "url": f"https://bitbucket.org/project-{x}/repository-{x}",
                "scm": "git",
                "language": "python",
                "description": f"some description {x}",
            }
            for x in range(5)
        ]

    # get all pull requests
    if kind == "pull-request":
        return [
            {
                "uuid": f"pull-request-{x}-{y}",
                "url": f"https://bitbucket.org/project-{x}/repository-{x}/pull-requests/{y}",
                "state": "OPEN",
                "author": f"user-{x % 3}",
            }
            for x in range(5)
            for y in range(2)
        ]

    # @todo - add components
    if kind == "component":
        return []

    return []


@ocean.on_resync("project")
async def resync_project(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for x in range(5):
        yield [
            {
                "uuid": f"project-{x}",
                "name": f"project-{x}",
                "url": f"https://bitbucket.org/project-{x}",
            }
        ]


@ocean.on_resync("repository")
async def resync_project(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for x in range(5):
        yield [
            {
                "uuid": f"repository-{x}",
                "name": f"repository-{x}",
                "url": f"https://bitbucket.org/project-{x}/repository-{x}",
                "scm": "git",
                "language": "python",
                "description": f"some description {x}",
            }
        ]


@ocean.on_resync("pull-request")
async def resync_project(_: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    for x in range(5):
        yield [
            {
                "uuid": f"pull-request-{x}",
                "url": f"https://bitbucket.org/project-{x}/repository-{x}/pull-requests/{x}",
                "state": "OPEN",
                "author": f"user-{x % 3}",
            }
        ]


# Listen to the `start` event of the integration. Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    print("Starting bitbucket-cloud-v2 integration")
