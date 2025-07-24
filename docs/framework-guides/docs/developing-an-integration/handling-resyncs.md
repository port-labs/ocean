---
title: Handling Resyncs
sidebar_label: 🔄 Handling Resyncs
sidebar_position: 6
---
# 🔄 Handling Resyncs

Resyncs are a core mechanism in Ocean integrations that enable data synchronization between your service and Port. This guide explains how to implement and handle resyncs effectively in your integration. The major point of entry for resync execution is the `main.py` file and this is done by using the `@ocean.on_resync` decorator to define the resync function.

## What are Resyncs Functions?

Resyncs functions are functions that:
- Fetch data from your service's API
- Transform the data into Port's expected format
- Send the data to Port in batches throught the ocean framework
- Run on a schedule or when triggered manually

## When are Resyncs Used?

Resyncs are triggered in several scenarios:
1. **Initial Data Load** - When the integration is first installed
2. **Scheduled Updates** - Based on your configured schedule
3. **Manual Triggers** - When users request a data refresh

## Core Components

Your integration needs these key components to handle resyncs:

1. **Client Initialization** - Setting up API communication
2. **Resource Kinds** - Defining data types
3. **Resync Functions** - Implementing data synchronization
4. **Webhook Registration** - Setting up real-time updates

## Client Initialization

The client initialization is responsible for creating and configuring the API client used throughout the integration. This is done by using the `ocean.integration_config` object to access the integration configuration and initializing the client with the necessary parameters. Jira and Octopus integrations use this approach to initialize the client. The init can be seperated into a separate file to avoid circular imports for large integrations.

<details>
<summary><b>Example: Jira Client Initialization</b></summary>

```python showLineNumbers
from port_ocean.context.ocean import ocean
from jira.jira_client import JiraClient

def create_jira_client() -> JiraClient:
    return JiraClient(
        jira_url=ocean.integration_config.get("jiraHost"),
        jira_email=ocean.integration_config.get("atlassianUserEmail"),
        jira_token=ocean.integration_config.get("atlassianUserToken"),
    )
```
</details>

<details>
<summary><b>Example: Octopus Client Initialization</b></summary>

```python showLineNumbers
from port_ocean.context.ocean import ocean
from client import OctopusClient

async def init_client() -> OctopusClient:
    client = OctopusClient(
        ocean.integration_config["server_url"],
        ocean.integration_config["octopus_api_key"],
    )
    return client
```
</details>

Key aspects:
- Reads configuration from `ocean.integration_config`
- Handles authentication setup
- Returns a configured client instance

## Resource Kinds

Resource kinds define the types of data your integration handles. They generally use an enum class to define the different types of data that can be synced. The enum class is imported into the `main.py` file and used as a parameter to the `@ocean.on_resync` decorator. The `ObjectKind` enum can be defined in an utils.py file and imported into the `main.py` file.

<details>
<summary><b>Example: Defining `ObjectKind` in Jira</b></summary>

```python showLineNumbers
# utils.py
from enum import StrEnum

class Kinds(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"

# main.py
from utils import Kinds

@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} issues")
        yield projects
```
</details>

<details>
<summary><b>Example: Defining `ObjectKind` in Octopus</b></summary>

```python showLineNumbers
# utils.py
from enum import StrEnum

class ObjectKind(StrEnum):
    SPACE = "space"
    PROJECT = "project"
    DEPLOYMENT = "deployment"
    RELEASE = "release"
    MACHINE = "machine"


# main.py
from utils import ObjectKind

@ocean.on_resync(ObjectKind.SPACE)
async def resync_spaces(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    octopus_client = await init_client()
    async for spaces in octopus_client.get_all_spaces():
        logger.info(f"Received batch {len(spaces)} spaces")
        yield spaces
```
</details>

Key points about resource kinds:
- Use `ObjectKind` as the standard enum class name
- Keep kinds in `main.py` if they're only used there
- Move to `utils.py` if needed in multiple files
- Use `StrEnum` for string-based enum values

## Resync Functions

Resync functions are the core of your integration's data synchronization. They are triggered by Port to fetch data from your service and submit it back to Port. These functions are decorated with `@ocean.on_resync()` and can be either kind-specific or handle all kinds.

### Resync Decorators

There are two ways to use the resync decorator:

1. **Kind-Specific Resync**
```python showLineNumbers
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # This function will only be called for PROJECT kind
    client = create_jira_client()
    async for projects in client.get_paginated_projects():
        yield projects
```

2. **Generic Resync**
```python showLineNumbers
@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # This function will be called for all kinds
    if kind == ObjectKind.SPACE:
        return
    client = await init_client()
    async for resources in client.get_paginated_resources(kind):
        yield resources
```

The choice between kind-specific and generic resync functions depends on your service's API pattern. Kind-specific resyncs, like those used in the Jira integration, are ideal when each resource type has unique API endpoints, requires different parameters, or needs resource-specific transformations. This approach allows for fine-grained control over how each resource type is handled.

On the other hand, generic resyncs, like those used in the Octopus integration, are more suitable when the API follows a consistent pattern across all resource types. This is the case when resources share the same base endpoint structure and use the same pagination and filtering logic. The Octopus API exemplifies this pattern, where all resources are accessed through a consistent base endpoint and are organized by spaces. In this case, the `kind` parameter is used to handle resource-specific variations while maintaining a single, unified resync function.

### Accessing Resource Configuration

The resource configuration is available through the `event` object imported from `port_ocean.context.event`. You only need to cast the resource config to the specific config type if you modified the integration config in the `integrations.py` file as described in [integration-configuration-and-kinds-in-ocean](integration-configuration-and-kinds-in-ocean.md). The resource config is available in the `event.resource_config` object.

```python showLineNumbers
from port_ocean.context.event import event

@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    # Access resource configuration
    selector = cast(ProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    client = create_jira_client()
    async for projects in client.get_paginated_projects(params):
        yield projects
```

### Example Implementations

<details>
<summary><b>Example: Jira Project Resync with Configuration</b></summary>

```python showLineNumbers
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()
    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects
```
</details>

<details>
<summary><b>Example: Octopus Multi-Space Resync</b></summary>

```python showLineNumbers
@ocean.on_resync()
async def resync_resources(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    if kind == ObjectKind.SPACE:
        return
    octopus_client = await init_client()
    async for spaces in octopus_client.get_all_spaces():
        tasks = [
            octopus_client.get_paginated_resources(kind, path_parameter=space["Id"])
            for space in spaces
            if space["Id"]
        ]
        async for batch in stream_async_iterators_tasks(*tasks):
            yield batch
```
</details>

### Resync Function Return Type

Resync functions must return an async generator that yields batches of resources:

```python
ASYNC_GENERATOR_RESYNC_TYPE = AsyncGenerator[list[dict[str, Any]], None]
```

Each batch should be a list of dictionaries representing your resources, with each dictionary containing the resource's data.


## Best Practices

1. **Code Organization**

   Maintain a clean and organized codebase by keeping client initialization separate from the main logic. Use clear and consistent naming conventions throughout your code, and ensure that each function's purpose is well-documented. This approach makes the code more maintainable and easier to understand for other developers.

2. **Error Handling**

   Implement comprehensive error handling throughout your integration. This includes logging errors with sufficient context to aid in debugging, handling edge cases gracefully, and implementing appropriate retry mechanisms for transient failures. Proper error handling ensures your integration remains robust and reliable in production environments.

3. **Performance**

   Optimize your integration's performance by leveraging async/await for I/O operations, processing data in manageable batches, and implementing caching for frequently accessed data. Be mindful of rate limits and implement appropriate throttling mechanisms to prevent overwhelming the service's API.

4. **Security**

   Ensure the security of your integration by using secure protocols, and properly handling authentication. Implement proper credential management and never expose sensitive information in logs or error messages. Regular security audits and updates are essential to maintain the integrity of your integration.

:::info Source Code
Example implementations are available in the [Jira](https://github.com/port-labs/ocean/tree/main/integrations/jira) and [Octopus](https://github.com/port-labs/ocean/tree/main/integrations/octopus) integration directories.
:::
