---
sidebar_position: 5
---

# ⚓ Implementing Webhooks
## Introduction

Port Ocean uses **webhook processors** to handle incoming Jira events (e.g., issue created, issue updated, project deleted). By **subclassing** `AbstractWebhookProcessor`, you define how to:

- **Authenticate** and **validate** webhook data.
- **Decide** whether a given event is relevant (e.g., “issue” vs. “project”).
- **Fetch** relevant data from Jira.
- **Return** updated or deleted data to Port.

You already have `AbstractWebhookProcessor` from the `port_ocean.core.handlers.webhook.abstract_webhook_processor` module. While we won’t include it directly here, you know it defines the main interface your processors must implement.


## Creating the `issue_webhook_processor.py` File

**Create** a folder named `webhook_processors` and add a file named `issue_webhook_processor.py` :

```console showLineNumbers
$ mkdir webhook_processors
$ touch webhook_processors/issue_webhook_processor
```

### Required Methods

`AbstractWebhookProcessor` requires you to implement (at minimum):

- **`should_process_event(event: WebhookEvent) -> bool`**\
  Decide if the event is relevant. For Jira issues, check if `event.payload["webhookEvent"]` starts with `"jira:issue_"`.
- **`get_matching_kinds(event: WebhookEvent) -> list[str]`**\
  Return the relevant kind(s) for the event (e.g., `["issue"]`).
- **`authenticate(...)`** and **`validate_payload(...)`**\
  Basic checks to ensure the request is from a valid source and the data is in the correct format.
- **`handle_event(payload: EventPayload, resource_config: ResourceConfig) -> WebhookEventRawResults`**\
  The core logic—fetch the updated or deleted data from Jira, then return it in the form Port expects.

### Issue Webhook Processor


<details>

<summary><b>Issue Webhook Processor (Click to expand)</b></summary>

```python showLineNumbers
from typing import Any, cast
from loguru import logger
from initialize_client import create_jira_client
from jira.overrides import JiraIssueConfig
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class IssueWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # For Jira issues, look for an event type like "jira:issue_created", etc.
        return event.payload.get("webhookEvent", "").startswith("jira:issue_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.ISSUE]

    async def handle_event(
        self,
        payload: EventPayload,
        resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # 1) Initialize the Jira client
        client = create_jira_client()
        config = cast(JiraIssueConfig, resource_config)

        # 2) Figure out if the issue was deleted
        webhook_type = payload.get("webhookEvent")
        issue_key = payload["issue"]["key"]
        logger.info(f"Fetching issue with key: {issue_key}")

        if webhook_type == "jira:issue_deleted":
            logger.info(f"Issue {issue_key} was deleted")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[payload["issue"]])

        # 3) Possibly apply a JQL filter
        params = {}
        if config.selector.jql:
            params["jql"] = f"{config.selector.jql} AND key = {issue_key}"
        else:
            params["jql"] = f"key = {issue_key}"

        # 4) Fetch the new data from Jira
        issues = []
        async for batch in client.get_paginated_issues(params):
            issues.extend(batch)

        if not issues:
            # If not found, instruct Port to delete it if it previously existed
            logger.warning(f"Issue {issue_key} not found with JQL: {params['jql']}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[payload["issue"]])

        # Otherwise, we want to update
        return WebhookEventRawResults(updated_raw_results=issues, deleted_raw_results=[])

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True  # Basic or token check could go here

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True  # Ensure required fields exist, etc.
```

</details>

This processor checks `webhookEvent` for `jira:issue_*` to confirm we’re dealing with an **issue** event, and then fetches the relevant issue with a JQL query.

## Creating the `project_webhook_processor.py` File

Similarly, for Jira **projects**, we create a `project_webhook_processor.py` file in the `webhook_processors` folder:

```console showLineNumbers
$ touch webhook_processors/project_webhook_processor.py
```

### Project Webhook Processor


<details>

<summary><b>Project Webhook Processor (Click to expand)</b></summary>

```python showLineNumbers
from loguru import logger
from initialize_client import create_jira_client
from kinds import Kinds
from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.handlers.webhook.abstract_webhook_processor import AbstractWebhookProcessor
from port_ocean.core.handlers.webhook.webhook_event import (
    EventHeaders,
    EventPayload,
    WebhookEvent,
    WebhookEventRawResults,
)


class ProjectWebhookProcessor(AbstractWebhookProcessor):
    async def should_process_event(self, event: WebhookEvent) -> bool:
        # For Jira projects, the event might be "project_updated", "project_deleted", etc.
        return event.payload.get("webhookEvent", "").startswith("project_")

    async def get_matching_kinds(self, event: WebhookEvent) -> list[str]:
        return [Kinds.PROJECT]

    async def authenticate(self, payload: EventPayload, headers: EventHeaders) -> bool:
        return True

    async def validate_payload(self, payload: EventPayload) -> bool:
        return True

    async def handle_event(
        self, payload: EventPayload, resource_config: ResourceConfig
    ) -> WebhookEventRawResults:
        # 1) Identify the project
        webhook_type = payload.get("webhookEvent", "")
        project_key = payload["project"]["key"]
        client = create_jira_client()

        if webhook_type == "project_soft_deleted":
            logger.info(f"Project {project_key} was deleted")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[payload["project"]])

        # 2) Otherwise fetch the updated project
        project_data = await client.get_single_project(project_key)
        if not project_data:
            logger.warning(f"Failed to retrieve project {project_key}")
            return WebhookEventRawResults(updated_raw_results=[], deleted_raw_results=[])

        # 3) Decide if it should be updated or deleted
        data_to_update = []
        data_to_delete = []

        if "deleted" in webhook_type:
            data_to_delete.append(project_data)
        else:
            data_to_update.append(project_data)

        return WebhookEventRawResults(updated_raw_results=data_to_update, deleted_raw_results=data_to_delete)
```

</details>

## How It Works

When Jira sends a **webhook** event to the integration:

1. Ocean routes the event through the `WebhookEvent` object, which includes the `payload` and `headers`.
2. Each **webhook processor** checks:
   - **`should_process_event(...)`** to see if it’s responsible for that event type.
   - **`authenticate(...)`** and **`validate_payload(...)`** to ensure it’s legitimate.
3. If relevant, `handle_event(...)` is called, where you:
   - Possibly fetch the updated Jira object (issue or project) using your `create_jira_client()`.
   - Return one or more items in the `updated_raw_results` or `deleted_raw_results` of `WebhookEventRawResults`.

Ocean then **maps** those raw results into your Port environment, using the rules in the `.port/resources/port-app-config.yml` file or in the integration mapping configuration on your Port dashboard



## Conclusion

We now have **two webhook processors**—`IssueWebhookProcessor` and `ProjectWebhookProcessor`—each in its own file, inheriting from `AbstractWebhookProcessor`. These classes define how to handle incoming Jira events for **issues** and **projects**, respectively. Key steps included:

1. Subclassing `AbstractWebhookProcessor` and overriding essential methods.
2. Checking the `webhookEvent` type (e.g., `"jira:issue_*"` vs. `"project_*"`) in `should_process_event`.
3. Using `create_jira_client()` to fetch the updated/deleted data from Jira.
4. Returning the data in a `WebhookEventRawResults` object so Ocean knows how to ingest it.

With webhook processors in place, **real-time** updates from Jira will flow seamlessly into Port. If you need to handle **additional** event types (like users or teams), simply create more processors in the same fashion.
