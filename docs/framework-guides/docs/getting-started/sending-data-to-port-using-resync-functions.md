---
sidebar_position: 6
---
# 📡 Sending Data to Port using Resync Functions

In this guide, we will learn how to **send data to Port using resync functions**. Resync functions are methods triggered by Port to fetch data from Jira and submit it back to Port in near-real-time. We’ll focus on:

1. **Initializing the Jira client** (via a `create_jira_client` function)
2. **Setting up webhooks** (so Jira events are automatically reported)
3. **Defining resync functions** for Jira **projects** and **issues**.

---

## Creating the `create_jira_client` Function

Rather than instantiating our `JiraClient` inline, we create a dedicated function in its own file—say, `initialize_client.py`—so it can be easily reused across the integration:

<details>

<summary><b>`initialize_client.py` file (Click to expand)</b></summary>

```python showLineNumbers
from port_ocean.context.ocean import ocean
from jira.jira_client import JiraClient  # or wherever JiraClient is defined

def create_jira_client() -> JiraClient:
    return JiraClient(
        jira_url=ocean.integration_config.get("jiraHost"),
        jira_email=ocean.integration_config.get("atlassianUserEmail"),
        jira_token=ocean.integration_config.get("atlassianUserToken"),
    )

```

</details>

- **`ocean.integration_config.get(...)`** reads credentials passed at runtime via environment variables. This is how Ocean supplies `jiraHost`, `atlassianUserEmail`, and `atlassianUserToken`.
- **`JiraClient`** is the client class we previously defined, capable of retrieving projects, issues, etc.

## Abstracting Kinds

To ensure we don't have to deal with specifying the kinds as raw strings, we will define them in an enum we can call. To do this, create a `kinds.py` file:

```console
$ touch kinds.py
```

Next, we define the `Kinds` enum:


<details>

<summary><b>`kinds.py` file (Click to expand)</b></summary>

```python showLineNumbers
from enum import StrEnum


class Kinds(StrEnum):
    PROJECT = "project"
    ISSUE = "issue"
```

</details>

## Setting Up Webhooks

Since we want live events from Jira, we will set up webhooks. Let’s define a small `setup_application` function for that. This will live in our main file:


<details>

<summary><b>Setting up webhooks in `main.py` (Click to expand)</b></summary>

```python showLineNumbers
from initialize_client import create_jira_client
from port_ocean.context.ocean import ocean
from loguru import logger

async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        return

    client = create_jira_client()
    await client.create_webhooks(base_url)
```

</details>

## Writing Resync Functions

Resync functions run whenever Port requests them—this can be on a schedule, or triggered manually. Each function is decorated with `@ocean.on_resync(...)` specifying which **kind** we want to sync.

Create a `main.py` file in the root folder of our integration:

```console
$ touch main.py
```

Here, we will

- Sync **projects** via `on_resync_projects`
- Sync **issues** via `on_resync_issues`
- Call `setup_application` on start to configure webhooks.


<details>

<summary><b>Writing resync functions in `main.py` (Click to expand)</b></summary>

```python showLineNumbers
import typing
from typing import cast

from loguru import logger
from port_ocean.context.event import event
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from kinds import Kinds  # your local definition: e.g., Kinds.PROJECT, Kinds.ISSUE
from initialize_client import create_jira_client

# Import the typed resource configs, e.g., JiraProjectResourceConfig, JiraIssueConfig
from jira.overrides import (
    JiraIssueConfig,
    JiraProjectResourceConfig,
)

async def setup_application() -> None:
    base_url = ocean.app.base_url
    if not base_url:
        return

    client = create_jira_client()
    # create_webhooks helps subscribe to real-time Jira updates
    await client.create_webhooks(base_url)

@ocean.on_resync(Kinds.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    # Retrieve the user’s config for the project kind.
    selector = cast(JiraProjectResourceConfig, event.resource_config).selector
    params = {"expand": selector.expand}

    async for projects in client.get_paginated_projects(params):
        logger.info(f"Received project batch with {len(projects)} projects")
        yield projects

@ocean.on_resync(Kinds.ISSUE)
async def on_resync_issues(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = create_jira_client()

    params = {}
    config = typing.cast(JiraIssueConfig, event.resource_config)

    # If a JQL filter is provided, add it to the request
    if config.selector.jql:
        params["jql"] = config.selector.jql
        logger.info(f"Found JQL filter: {config.selector.jql}... Adding to request.")

    # If specific fields are requested, add them
    if config.selector.fields:
        params["fields"] = config.selector.fields

    async for issues in client.get_paginated_issues(params):
        logger.info(f"Received issue batch with {len(issues)} issues")
        yield issues

# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")

    # If we’re only running once and exiting, no need for webhooks.
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()

```

</details>

### Explanation

1. **`@ocean.on_resync(Kinds.PROJECT)`**: Ties each function to a particular **kind**—for example, when a "project" resync is requested, `on_resync_projects` is called.
2. **Using `event.resource_config`**: We cast the resource config to the relevant selector class (e.g., `JiraProjectResourceConfig`) so we can parse user-defined parameters like `expand` or `jql`.
3. **Async Generators**: Each function yields data in batches. Port collects and processes them into the `port-app-config.yml` mapping.


## Adding Webhook Handling
Webhooks are represented in Port through FastAPI endpoints. When Jira sends a webhook to the predefined webhook route (usually `/webhook`), Port processes the event and sends it to the relevant webhook processor. We'll add the webhook processors we defined in the previous step to our `main.py` file:

<details>

<summary><b>Adding webhook handling to `main.py` (Click to expand)</b></summary>

```python showLineNumbers
... # Existing imports
# highlight-start
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
# highlight-end


... # Existing code

# Called once when the integration starts.
@ocean.on_start()
async def on_start() -> None:
    logger.info("Starting Port Ocean Jira integration")

    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping webhook creation because the event listener is ONCE")
        return

    await setup_application()


ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)

```

</details>

### Explanation

- **`ocean.add_webhook_processor`**: Registers the webhook processors we defined in the previous step. This tells Port to call `IssueWebhookProcessor` when it receives an issue-related event, and `ProjectWebhookProcessor` for project-related events.


## Putting It All Together

At the end of this guide, you should now have:

- An `initialize_client.py` file with a `create_jira_client` function.
- A `main.py` file that includes:
  - **Resync functions** (`@ocean.on_resync`) for the relevant kinds (projects, issues).
  - A `@ocean.on_start` function to set up webhooks
  - Webhook processors for handling incoming Jira events.

With these components, your Jira integration is ready to fetch data and push it into Port!

## Guidelines for Writing Resync Functions

- **Avoid blocking operations**: Resync functions should be non-blocking and return quickly.
- **Use async generators**: Yield data in batches to avoid memory issues.
- **Handle errors gracefully**: Implement error handling to manage and log errors.
- **Use resource configs**: Cast resource configs to relevant selectors to access user-defined parameters.

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::
