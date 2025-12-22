---
title: Event Listeners Architecture
sidebar_label: 🔈 Event Listeners Architecture
sidebar_position: 3
description: How event listeners work in Ocean framework
---

# 🔈 Event Listeners Architecture

Event listeners are the entry point for resync requests. They monitor Port for configuration changes or resync requests.

## Types of Event Listeners

1. **POLLING**: Queries Port API at intervals
2. **KAFKA**: Consumes messages from Kafka topic
3. **WEBHOOK**: Receives HTTP requests from Port
4. **ONCE**: Runs resync once and exits
5. **WEBHOOKS_ONLY**: Only processes webhooks, no resync
6. **ACTIONS_ONLY**: Only processes actions, no resync

## Event Listener Flow

When an event listener detects a resync request:

```mermaid
flowchart LR
    A["Event Detected"] -->|Before Resync| B["Update Port Status<br/>'running'"]
    B -->|Execute Resync| C["sync_raw_all()"]
    C -->|Success| D["Update Port Status<br/>'completed'"]
    C -->|Failure| E["Update Port Status<br/>'failed'"]

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#e1ffe1
    style E fill:#ffe1e1
```

**Steps**:
1. **Before Resync**: Updates Port with "running" status
2. **Execute Resync**: Calls `sync_raw_all()`
3. **After Resync**: Updates Port with "completed" status
4. **On Failure**: Updates Port with "failed" status

## How Event Listeners Work

Each event listener type implements the `BaseEventListener` interface and follows this pattern:

1. **Monitor**: Continuously monitors for resync requests (polling, Kafka messages, HTTP requests)
2. **Detect**: Detects when a resync is needed (configuration change, explicit request)
3. **Trigger**: Calls the resync handler (`sync_raw_all()`)
4. **Track**: Updates Port with the resync status throughout the process

For more details on configuring and using event listeners, see the [Event Listener](../features/event-listener.md) documentation.
