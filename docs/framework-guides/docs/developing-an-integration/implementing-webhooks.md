---
sidebar_position: 4
---

# ⚓ Implementing Live Events

## Introduction

Live events are a crucial part of any integration, allowing real-time updates from your service to be reflected in Port. Port Ocean uses **live event processors** (implemented via `AbstractWebhookProcessor`) to handle incoming events from your service. By **subclassing** `AbstractWebhookProcessor`, you define how to:

- **Authenticate** and **validate** live event data
- **Decide** whether a given event is relevant
- **Fetch** relevant data from your service
- **Return** updated or deleted data to Port

:::note Terminology
While we use "live events" in documentation, the underlying implementation uses webhooks (HTTP POST requests). The code still references "webhook" in class names and modules (e.g., `AbstractWebhookProcessor`, `WebhookEvent`) for technical accuracy.
:::

You already have `AbstractWebhookProcessor` from the `port_ocean.core.handlers.webhook.abstract_webhook_processor` module. This base class defines the main interface your processors must implement.

## Creating Live Event Processors

Let's look at how to implement live event processors. We'll use Jira as an example, but the concepts apply to any service.

### Required Methods

`AbstractWebhookProcessor` requires you to implement these key methods:

- **`should_process_event(event: WebhookEvent) -> bool`**\
  Determines if this processor should handle the event. Check event type, payload structure, etc.
- **`get_matching_kinds(event: WebhookEvent) -> list[str]`**\
  Returns the resource kinds this event affects (e.g., `["issue"]`, `["project"]`).
- **`authenticate(...)`** and **`validate_payload(...)`**\
  Ensures the request is legitimate and the data is valid.
- **`handle_event(...)`**\
  Core logic for processing the event and returning results.

### Example Implementation

Here's how Jira implements live event processors for issues and projects. This is just one example - your implementation will depend on your service's event structure.

#### Issue Live Event Processor

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

#### Project Live Event Processor

<details>
<summary><b>Project Live Event Processor (Click to expand)</b></summary>

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

## Live Event Processor Registration

In the `main.py` file of your integration, you must register live event processors that handle different types of events.
This will allow the integration to start the processors which will receive live events from your service and process them accordingly.

<details>
<summary><b>Example: Jira Live Event Processor Registration</b></summary>

```python showLineNumbers
from port_ocean.context.ocean import ocean
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.user_webhook_processor import UserWebhookProcessor

# All other content of the main.py file

# Register live event processors for different resource types
ocean.add_webhook_processor("/webhook", IssueWebhookProcessor)
ocean.add_webhook_processor("/webhook", ProjectWebhookProcessor)
ocean.add_webhook_processor("/webhook", UserWebhookProcessor)
```
</details>

For an overview of live events and when to use processors vs direct endpoints, see the [Live Events](../framework/features/live-events.md) guide.

## How Live Events Work in Ocean

When your service sends a live event (via webhook) to the integration:

1. **Event Reception**
   - Ocean receives the live event via HTTP POST
   - Creates a `WebhookEvent` object with payload and headers
   - Adds the event to a processing queue

2. **Processor Selection**
   - Each processor checks `should_process_event`
   - Only relevant processors handle the event

3. **Event Processing**
   - Processors authenticate and validate the event
   - Fetch updated data from your service
   - Return results in `WebhookEventRawResults`

4. **Port Update**
   - Ocean maps the results to Port entities using JQ transformations
   - Updates or deletes entities as needed

:::tip Live Event Flow
The live event flow follows this pattern:
```
Service Event → Live Event Processor → Data Fetching → Port Update
```
:::

## Best Practices for Live Event Implementation

1. **Security**
   - Always implement proper authentication in `authenticate()`
   - Validate event payloads in `validate_payload()`
   - Use secure communication channels (HTTPS)

2. **Error Handling**
   - Handle missing or invalid data gracefully
   - Leverage built-in retry mechanisms (configure `max_retries`, etc.)
   - Log errors for debugging

3. **Performance**
   - Keep processors focused and single-purpose
   - Use `should_process_event()` to filter events early
   - Fetch only necessary data from your service

4. **Maintenance**
   - Document event types and payloads
   - Monitor live event processing performance
   - Test authentication and validation logic thoroughly

Remember, the Jira example above is just one way to implement live events. Your implementation will depend on your service's event structure and requirements.
