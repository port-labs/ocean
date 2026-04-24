---
title: Actions
sidebar_label: ⚡ Actions
sidebar_position: 8
description: Understand how the Ocean framework executes integration actions
---

# ⚡ Actions

The Ocean framework provides a robust system for executing integration actions. Actions are user-initiated operations that are executed on resources in third-party services through Port. The framework handles the orchestration, queuing, rate limiting, and error management of these operations.

## Overview

Actions provide a critical backstream capability in Ocean: they allow Port and its users not only to pull data from third-party systems, but also to write data or trigger changes back in those systems. Typical use cases include remediating issues (e.g., restarting a resource, unlocking an account), provisioning resources, or invoking custom workflows such as syncing state or rotating credentials.

Actions can be used to perform operations on any external resource or service your integration can access, regardless of whether that resource is explicitly modeled within your integration.

When a user triggers an action in Port, the Ocean framework ensures the action is reliably queued and executed by the relevant integration. The framework abstracts away concurrency, API rate limiting, and error handling, so actions are processed predictably and can scale as needed.

### Key Components

The action execution system consists of three main components:

1. **Executor** - The integration-specific logic that performs the actual action
2. **Execution Manager** - Orchestrates executors, manages queues, and handles worker distribution
3. **Queue System** - Buffers action runs and ensures sequential or parallel execution as needed

## Execution Flow

Here's how an action flows through the system:

```
1. User performs action in Port
   ↓
2. Port publishes action run to Ocean integration
   ↓
3. Execution Manager polls for new action runs
   ↓
4. Runs are queued based on partition keys
   ↓
5. Workers process runs from queues (round-robin)
   ↓
6. Executor performs action and handles results
   ↓
7. Status is reported back to Port
```

## Core Concepts

### Action Executors

An **Action Executor** is a class that implements the integration-specific logic for a particular action. Each action type in your integration needs its own executor.

Key responsibilities:
- Execute the actual business logic (API calls, resource updates, etc.)
- Manage rate limiting to prevent API quota exhaustion
- Handle action parameters and validation
- Report results back to Port

### Execution Manager

The **Execution Manager** is the orchestrator that:
- Polls Port for pending action runs
- Distributes runs across worker tasks
- Manages multiple concurrent workers
- Handles graceful shutdown
- Monitors queue sizes with a high-watermark system

### Queue System

The framework uses queues to buffer and manage action runs:

- **Global Queue** - For actions that can run in parallel (non-partitioned)
- **Partition Queues** - For actions that must run sequentially per partition key

#### Partitioning Example

When executing a "deploy" action, you might want all deployments to the same resource to happen sequentially to avoid conflicts:

```python
async def _get_partition_key(self, run: ActionRun) -> str | None:
    params = run.payload.integrationActionExecutionProperties
    resource_id = params.get("resource_id")
    return resource_id  # Runs with same resource_id execute sequentially
```

Runs without a partition key execute in parallel through the global queue.

## Worker Pool & Round-Robin Distribution

The Execution Manager maintains a pool of worker tasks that process action runs. Workers use a round-robin strategy to distribute work across queues:

- **Multiple Workers** - The system spawns configurable number of workers to process runs concurrently
- **Round-Robin** - Workers take turns pulling from active sources (global or partition queues)
- **Load Distribution** - This ensures fair distribution of work across all queues

### Worker Lifecycle

Workers continuously:
1. Wait for an active source (queue with pending runs)
2. Process a single run from that queue
3. Return to step 1 until shutdown

If no sources have pending runs, workers wait for new activity or shutdown signal.

## Rate Limiting

The framework includes built-in support for API rate limiting to prevent quota exhaustion:

```python
async def is_close_to_rate_limit(self) -> bool:
    """Check if approaching rate limit threshold (e.g., 10% remaining)"""
    rate_info = await self.client.get_rate_limit_info()
    return rate_info.remaining / rate_info.limit < 0.1

async def get_remaining_seconds_until_rate_limit(self) -> float:
    """Return seconds to wait for rate limit to reset"""
    rate_info = await self.client.get_rate_limit_info()
    if rate_info.reset_time > datetime.now():
        return (rate_info.reset_time - datetime.now()).total_seconds()
    return 0.0
```

When the execution manager detects an approaching rate limit:
1. It pauses run execution
2. Logs the delay with backoff time (capped at 10 seconds max)
3. Waits for the specified duration
4. Resumes execution

## High Watermark Flow Control

The framework implements a high-watermark system to prevent queue overload:

- **High Watermark** - Maximum total size across all queues (default: 1000 runs)
- **Poll Throttling** - When queues reach the watermark, polling pauses
- **Automatic Resume** - Polling resumes once workers process runs and free up space

This prevents memory issues and ensures steady-state operation.

## Deduplication

The system prevents duplicate processing of the same run:

- Each run is tracked by its unique ID
- When a run is added to a queue, it's marked as in-progress
- If the same run arrives again before processing completes, it's skipped
- The ID is removed from tracking after successful processing or commit

## Graceful Shutdown

The framework handles shutdown gracefully:

1. Sets shutdown flag to stop new work
2. Allows current workers to complete their tasks
3. Cancels polling task
4. Waits for all workers to finish (configurable timeout)
5. Performs cleanup and logs completion

## Error Handling

Errors during action execution are managed comprehensively:

- **Execution Errors** - Caught and reported back to Port with error summary
- **Rate Limit Errors** - Automatically backed off and retried
- **Acknowledgment Errors** - If run is already being processed by another worker, execution is skipped
- **Validation Errors** - Early validation prevents invalid runs from entering queues

## Webhook Processors

For asynchronous action status updates, executors can optionally provide webhook processors:

```python
class MyActionExecutor(AbstractExecutor):
    ACTION_NAME = "my_action"
    WEBHOOK_PROCESSOR_CLASS = MyWebhookProcessor  # Optional
    WEBHOOK_PATH = "/webhook/my_action"  # Optional
```

Webhook processors allow the integration to receive external events (e.g., from the third-party service) and update run status in Port asynchronously.

## Configuration

The Execution Manager is configured with these parameters:

| Parameter | Description | Default |
| --------- | ----------- | ------- |
| `workers_count` | Number of concurrent worker tasks | `1` |
| `runs_buffer_high_watermark` | Maximum queue size before throttling polls | `1000` |
| `poll_check_interval_seconds` | Seconds between polling attempts | `5` |
| `visibility_timeout_ms` | Timeout for claimed runs (milliseconds) | `30000` |
| `max_wait_seconds_before_shutdown` | Maximum time to wait during graceful shutdown | `30` |

## Implementation Guide

### Creating an Action Executor

```python
from port_ocean.core.handlers.actions import AbstractExecutor
from port_ocean.core.models import ActionRun, RunStatus
from port_ocean.context.ocean import ocean

class MyIntegrationActionExecutor(AbstractExecutor):
    ACTION_NAME = "my_action"  # Match your spec.yaml action name
    PARTITION_KEY = "resource_id"  # Optional: for sequential execution
    WEBHOOK_PROCESSOR_CLASS = None  # Optional: for async updates
    WEBHOOK_PATH = "/webhook/my_action"  # Optional

    async def is_close_to_rate_limit(self) -> bool:
        # Implement rate limit check logic
        return False

    async def get_remaining_seconds_until_rate_limit(self) -> float:
        # Implement rate limit wait time logic
        return 0.0

    async def execute(self, run: ActionRun) -> None:
        # Extract parameters
        params = run.payload.integrationActionExecutionProperties
        resource_id = params.get("resource_id")

        if not resource_id:
            raise ValueError("resource_id is required")

        # Perform the action
        result = await self.api_client.update_resource(
            resource_id,
            **params
        )

        # Update run status
        await ocean.port_client.patch_run(
            run.id,
            {
                "status": RunStatus.SUCCESS,
                "summary": f"Successfully updated resource {resource_id}"
            }
        )
```

### Registering Executors

Executors are registered with the Execution Manager during integration setup:

```python
execution_manager = ExecutionManager(...)
execution_manager.register_executor(MyIntegrationActionExecutor(api_client))
await execution_manager.start_processing_action_runs()
```

## Best Practices

1. **Implement Rate Limiting** - Always implement rate limit checks to prevent API quota issues
2. **Use Partition Keys** - When actions must be sequential, implement partition keys to avoid conflicts
3. **Validate Parameters** - Validate action parameters early in the execute method
4. **Error Messages** - Provide clear error messages when actions fail
5. **Logging** - Use structured logging for debugging action issues
6. **Webhook Processors** - Use webhook processors for long-running operations to provide real-time updates

## Additional Resources

- [Advanced Configuration Guide](../advanced-configuration.md)
- [Integration Development Guide](../../developing-an-integration/developing-an-integration.md)
- [Framework Overview](../framework.md)
