---
sidebar_position: 4
---

# 📡 Sending Data to Port using Resync Functions

In this guide, we will learn how to send data to Port using resync functions. Resync functions are functions that are executed by Port to retrieve data from a source and send it to Port.

Since this is the entry point of the integration, this will be done in `main.py` file. Delete the contents of the file.

However, before we write resync functions, we need to set up a few things.


## Initializing the `GitHubClient` class
The `GitHubClient` class has two parameters that can be passed to its constructor:

- `base_url`: The base URL of the GitHub API. This is set to `https://api.github.com` by default.
- `access_token`: The access token to authenticate with the GitHub API. This is required if the resources you want to access are private.

We expect users to pass these values via environment variables. Since Ocean loads these variables differently, we will use a globally accessible configuration dictionary with the values  populated by Ocean at runtime to access these values.



<details>

<summary><b>Initializing the `GitHubClient` class</b></summary>

```python showLineNumbers title="main.py"
# highlight-start
from port_ocean.context.ocean import ocean

from client import GitHubClient


def initialize_github_client() -> GitHubClient:
    return GitHubClient(
        base_url=ocean.integration_config.get("base_url", "https://api.github.com"),
        access_token=ocean.integration_config.get("access_token"),
    )

# highlight-end

```

</details>


## Writing Resync Functions
### Syncing Organizations
The first resync function we will write is to sync organizations. This function will retrieve a list of organizations from GitHub and send it to Port.

<details>

<summary><b>Syncing Organizations</b></summary>

```python showLineNumbers title="main.py"
# highlight-start
from typing import cast

from loguru import logger
from port_ocean.context.event import event
# highlight-end
from port_ocean.context.ocean import ocean
# highlight-next-line
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import GitHubClient
# highlight-start
from integration import (
    ObjectKind,
    GitHubOranizationResourceConfig,
)
# highlight-end



@ocean.on_resync(ObjectKind.ORGANIZATION)
async def get_organizations(
    kind: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_github_client()
    selector = cast(GitHubOranizationResourceConfig, event.resource_config).selector
    logger.info(f"Retrieving organizations: {selector.organizations}")
    organizations = await client.get_organizations(selector.organizations)
    logger.info(f"Retrieved organization batch of size: {len(organizations)}")
    yield organizations

```

</details>

The `@ocean.on_resync` decorator is used to register the function as a resync function. The function is called with the kind of object to sync. The function should return an asynchronous generator that yields the data to be sent to Port or a list of objects containing data to be sent to Port.

In addition, the `event` object is used to access the resource configuration and other information about the event that triggered the resync function. Using this, we can retrieve the user-defined configuration for the resource and use it to fetch the data from the source.

### Syncing Repositories
Syncing repositories is similar to syncing organizations. The only difference is that we will be using the `GitHubRepositoryResourceConfig` class instead of the `GitHubOrganizationResourceConfig ` class.

<details>

<summary><b>Syncing Repositories</b></summary>

```python showLineNumbers title="main.py"
# rest of the imports
from integration import (
    ObjectKind,
    GitHubOrganizationResourceConfig,
# highlight-next-line
    GitHubRepositoryResourceConfig,
)


# rest of the code


# highlight-start
@ocean.on_resync(ObjectKind.REPOSITORY)
async def get_repositories(
    kind: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_github_client()
    selector = cast(GitHubRepositoryResourceConfig, event.resource_config).selector
    logger.info(f"Retrieving {selector.type} repositories for organizations: {selector.organizations}")
    async for repositories in client.get_repositories(
        selector.organizations,
        selector.type
    ):
        logger.info(f"Retrieved repository batch of size: {len(repositories)}")
        yield repositories

# highlight-end

```

</details>

### Syncing Pull Requests
Syncing pull requests is similar to syncing repositories. The only difference is that we will be using the `GitHubPullRequestResourceConfig` class instead of the `GitHubOrganizationResourceConfig ` class.


<details>

<summary><b>Syncing Pull Requests</b></summary>

```python showLineNumbers title="main.py"
# rest of the imports
from integration import (
    ObjectKind,
    GitHubOrganizationResourceConfig,
    GitHubRepositoryResourceConfig,
# highlight-next-line
    GitHubPullRequestResourceConfig,
)


# rest of the code

@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def get_pull_requests(
    kind: str
) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_github_client()
    selector = cast(GitHubPullRequestResourceConfig, event.resource_config).selector
    logger.info(f"Retrieving {selector.state} pull requests for organizations: {selector.organizations}")
    async for pull_requests in client.get_pull_requests(
        selector.organizations,
        selector.type,
        selector.state
    ):
        logger.info(f"Retrieved pull request batch of size: {len(pull_requests)}")
        yield pull_requests

```

</details>


## Conclusion
In this guide, we learned how to send data to Port using resync functions. We initialized the `GitHubClient` class and wrote resync functions to sync organizations, repositories, and pull requests. These functions will be executed by Port to retrieve data from GitHub and send it to Port.

At the end of this section, your `main.py` file` should look like this:

<details>

<summary><b>`main.py`</b></summary>

```python showLineNumbers title="main.py"
from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import GitHubClient
from integration import (
    GitHubOranizationResourceConfig,
    GitHubPullRequestResourceConfig,
    GitHubRepositoryResourceConfig,
    ObjectKind,
)


def initialize_github_client() -> GitHubClient:
    return GitHubClient(
        base_url=ocean.integration_config.get("base_url", "https://api.github.com"),
        access_token=ocean.integration_config.get("access_token"),
    )


@ocean.on_resync(ObjectKind.ORGANIZATION)
async def get_organizations(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_github_client()
    selector = cast(GitHubOranizationResourceConfig, event.resource_config).selector
    logger.info(f"Retrieving organizations: {selector.organizations}")
    organizations = await client.get_organizations(selector.organizations)
    logger.info(f"Retrieved organization batch of size: {len(organizations)}")
    yield organizations


@ocean.on_resync(ObjectKind.REPOSITORY)
async def get_repositories(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_github_client()
    selector = cast(GitHubRepositoryResourceConfig, event.resource_config).selector
    logger.info(
        f"Retrieving {selector.type} repositories for organizations: {selector.organizations}"
    )
    async for repositories in client.get_repositories(
        selector.organizations, selector.type
    ):
        logger.info(f"Retrieved repository batch of size: {len(repositories)}")
        yield repositories


@ocean.on_resync(ObjectKind.PULL_REQUEST)
async def get_pull_requests(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = initialize_github_client()
    selector = cast(GitHubPullRequestResourceConfig, event.resource_config).selector
    logger.info(
        f"Retrieving {selector.state} pull requests for organizations: {selector.organizations}"
    )
    async for pull_requests in client.get_pull_requests(
        selector.organizations, selector.type, selector.state
    ):
        logger.info(f"Retrieved pull request batch of size: {len(pull_requests)}")
        yield pull_requests

```

</details>

:::tip Source Code
You can find the source code for the integration in the [Developing An Integration repository on GitHub](https://github.com/port-labs/developing-an-integration)

:::

Next, we will define default blueprints and mappings for the resources we are syncing.
