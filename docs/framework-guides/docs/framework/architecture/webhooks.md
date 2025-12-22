---
title: Webhook Processing Architecture
sidebar_label: 🪝 Webhook Processing Architecture
sidebar_position: 5
description: How Ocean processes webhooks from third-party systems
---

# 🪝 Webhook Processing Architecture

Ocean processes webhooks from third-party systems to provide real-time updates to Port.

## Webhook Flow

```mermaid
flowchart TD
    A["Third-party System<br/>sends webhook"] -->|HTTP POST| B["Ocean receives webhook"]
    B -->|Find matching processors| C["Webhook Processors"]
    C -->|Authenticate & validate| D["Authentication<br/>& Validation"]
    D -->|Valid| E["Fetch updated data<br/>from 3rd-party API"]
    D -->|Invalid| F["Reject webhook"]
    E -->|Transform data| G["Entity Processor<br/>(JQ Transformation)"]
    G -->|Apply changes| H["State Applier<br/>Update Port"]

    style A fill:#e1f5ff
    style B fill:#fff4e1
    style C fill:#ffe1f5
    style D fill:#fff4e1
    style E fill:#e1ffe1
    style F fill:#ffe1e1
    style G fill:#e1ffe1
    style H fill:#e1f5ff
```

## Webhook Processing Steps

1. **Receive webhook**: Ocean receives HTTP POST request from third-party system
2. **Find matching processors**: Ocean identifies which webhook processors should handle this event
3. **Authenticate and validate**: Processors verify the webhook is legitimate and payload is valid
4. **Fetch updated data**: Processors fetch the latest data from the third-party API (webhook payloads often don't contain complete data)
5. **Transform and apply changes**: Data is transformed using JQ mappings and applied to Port

## Key Differences from Resync

Webhook processing differs from resync in several ways:

- **Triggered by external events**: Webhooks are triggered by third-party systems, not Port
- **Processes single resources**: Typically handles one resource at a time (the one that changed)
- **Real-time**: Updates happen immediately when events occur
- **Selective**: Only processes events that match configured webhook processors

For more details on implementing webhook processors, see the [Implementing Webhooks](../../developing-an-integration/implementing-webhooks.md) guide.
