---
title: Framework Internals
sidebar_label: ⚙️ Framework Internals
sidebar_position: 6
description: Internal mechanisms of Ocean framework including event context, metrics, error handling, and caching
---

# ⚙️ Framework Internals

This document covers the internal mechanisms that power Ocean framework, including event context, metrics, error handling, and caching.

## Event Context

Ocean uses an event context system to track execution and provide access to configuration and shared data throughout the event lifecycle.

### Using Event Context

```python
async with event_context(EventType.RESYNC, trigger_type="machine"):
    # All code here has access to event context
    event.resource_config  # Current resource config
    event.port_app_config  # Port app config
    event.attributes  # Shared attributes/cache
```

### Event Context Properties

**Event context provides**:
- `event.type`: Event type (resync, start, http_request)
- `event.trigger_type`: How event was triggered (manual, machine, request)
- `event.resource_config`: Resource configuration for current resync
- `event.port_app_config`: Complete Port app configuration
- `event.attributes`: Dictionary for sharing data between functions

### Event Context Lifecycle

The event context is automatically created when an event starts and provides:
- **Isolation**: Each event has its own context
- **Inheritance**: Nested events inherit from parent context
- **Caching**: `event.attributes` can be used to cache data within an event
- **Abort support**: Events can be aborted if a newer event is triggered

## Metrics and Monitoring

Ocean tracks comprehensive metrics throughout the resync process to provide visibility into integration performance and health.

### Metrics Tracked

**Object counts**:
- Created entities
- Updated entities
- Deleted entities
- Failed entities

**Sync state**:
- Syncing
- Completed
- Failed
- Aborted

**Timing metrics**:
- Extract phase duration
- Transform phase duration
- Load phase duration
- Total resync duration

**Resource kind metrics**:
- Per-kind entity counts
- Per-kind processing times
- Per-kind error rates

### Metrics Reporting

**Metrics are reported to**:
- **Prometheus**: If enabled, metrics are exposed via Prometheus endpoint
- **Port webhook**: If configured, metrics are sent to Port for visualization
- **Logs**: All metrics are logged for debugging and monitoring

## Error Handling

Ocean implements comprehensive error handling to ensure reliability and provide clear error information.

### Resync Abort

If a new resync is triggered while one is running:

**What happens**:
- Current resync is aborted gracefully
- New resync starts immediately
- Partial state may remain (entities already processed are kept)
- Metrics are updated to reflect abort status

**Use cases**:
- Configuration changes trigger new resync
- Manual resync requested while automatic resync is running
- Scheduled resync overlaps with in-progress resync

### Error Recovery

Ocean implements robust error recovery:

**Error handling**:
- Collects errors during processing without stopping
- Continues processing other batches even if one fails
- Raises `ExceptionGroup` at end if errors occurred
- Logs all errors with context for debugging

**Error types handled**:
- API errors from third-party systems
- Transformation errors (JQ mapping failures)
- Port API errors
- Network timeouts
- Access denied errors

### Error Reporting

Errors are:
- **Logged**: Detailed error information is logged
- **Tracked**: Error counts are included in metrics
- **Reported**: Errors are reported to Port (if configured)
- **Preserved**: Error details are maintained for debugging

## Caching

Ocean uses caching to optimize performance and reduce API calls.

### Cache Lifecycle

**Cache is cleared**:
- Before resync starts (ensures fresh data)
- After resync completes (cleanup)

**Cache is used for**:
- Port app config (unless `use_cache=False`)
- Entity state lookups
- Related entities
- Configuration data

### Cache Strategy

Ocean's caching strategy:
- **Event-scoped**: Cache is scoped to events
- **Automatic invalidation**: Cache is cleared at appropriate times
- **Configurable**: Can be disabled for specific operations
- **Memory-efficient**: Uses efficient caching mechanisms

### When to Disable Cache

You may want to disable caching when:
- Debugging configuration issues
- Testing configuration changes
- Ensuring absolute data freshness
- Troubleshooting cache-related problems

Use `use_cache=False` when fetching Port app config to bypass cache.
