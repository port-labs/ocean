---
title: Event Listener-Specific Startup
sidebar_label: 🚀 Event Listener Startup
sidebar_position: 7
description: Configure different startup behavior for different event listener types
---

# 🚀 Event Listener-Specific Startup

Ocean integrations can define different startup behaviors for each event listener type using the `@ocean.on_start(event_listener=...)` decorator.

## Problem Solved

Previously, integrations had to manually check the event listener type in their startup code:

```python
@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping external setup because the event listener is ONCE")
        return

    # External service setup logic
    await setup_external_services()
```

## New Solution

With event listener-specific startup decorators, you can define clean, separate functions:

```python
from port_ocean import EventListenerType

@ocean.on_start(event_listener=EventListenerType.ONCE)
async def on_start_once() -> None:
    logger.info("Starting in ONCE mode - minimal setup needed")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.KAFKA)
async def on_start_kafka() -> None:
    logger.info("Starting in KAFKA mode")
    await setup_credentials()
    await setup_kafka_consumer()
```

## Supported Event Listener Types

- **`ONCE`**: Single execution, then exit
- **`POLLING`**: Periodic change detection
- **`KAFKA`**: Real-time events via Kafka
- **`WEBHOOKS_ONLY`**: Only handles webhooks, no periodic syncs

## Using the EventListenerType Enum

Import and use the enum for type safety:

```python
from port_ocean import EventListenerType

# Available enum values:
EventListenerType.ONCE
EventListenerType.POLLING
EventListenerType.KAFKA
EventListenerType.WEBHOOKS_ONLY
```

### Benefits
- **Type Safety**: Prevents typos like `"KAFK"` instead of `"KAFKA"`
- **IDE Support**: Autocompletion shows all available types
- **Error Prevention**: Catch mistakes at development time

## Basic Usage

### Single Event Listener Type

```python
@ocean.on_start(event_listener=EventListenerType.ONCE)
async def on_start_once() -> None:
    """Startup for ONCE mode - typically minimal setup needed"""
    logger.info("Starting in ONCE mode")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.KAFKA)
async def on_start_kafka() -> None:
    """Startup for KAFKA mode - setup Kafka consumer"""
    logger.info("Starting in KAFKA mode")
    await setup_credentials()
    await setup_kafka_consumer()

@ocean.on_start(event_listener=EventListenerType.POLLING)
async def on_start_polling() -> None:
    """Startup for POLLING mode - minimal setup needed"""
    logger.info("Starting in POLLING mode")
    await setup_credentials()
```

### Using String Literals (Also Supported)

```python
# String literals work too for backwards compatibility
async def setup_kafka_consumer() -> None:
    """Kafka consumer setup logic"""
    # Setup Kafka consumer
    pass

# Create consumers for real-time events

@ocean.on_start(event_listener="ONCE")
async def on_start_once() -> None:
    # Skip external setup for ONCE mode
    pass

@ocean.on_start(event_listener="KAFKA")
async def on_start_kafka() -> None:
    await setup_kafka_consumer()
```

## Advanced Patterns

### Before vs After

**Before (Manual Checks):**
```python
@ocean.on_start()
async def on_start() -> None:
    if ocean.event_listener_type == "ONCE":
        logger.info("Skipping external setup because the event listener is ONCE")
        return

    await setup_external_services()
```

**After (Clean Separation):**
```python
@ocean.on_start(event_listener=EventListenerType.ONCE)
async def on_start_once() -> None:
    logger.info("Starting in ONCE mode - minimal setup needed")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.KAFKA)
async def on_start_kafka() -> None:
    logger.info("Starting in KAFKA mode")
    await setup_credentials()
    await setup_kafka_consumer()

@ocean.on_start(event_listener=EventListenerType.POLLING)
async def on_start_polling() -> None:
    logger.info("Starting in POLLING mode - minimal setup needed")
    await setup_credentials()
```

### Multiple Functions for Same Event Listener

```python
# You can register multiple functions for the same event listener type
@ocean.on_start(event_listener=EventListenerType.KAFKA)
async def setup_kafka_credentials() -> None:
    await setup_credentials()

# This will be used for KAFKA mode
@ocean.on_start(event_listener="KAFKA")
async def setup_kafka_consumer() -> None:
    await setup_kafka_consumer()
```

### Excluding Specific Event Listeners

Use multiple decorators to run the same function for multiple event listeners:

```python
# This function runs for KAFKA, POLLING, and WEBHOOKS_ONLY but NOT ONCE
@ocean.on_start(event_listener=EventListenerType.KAFKA)
@ocean.on_start(event_listener=EventListenerType.POLLING)
@ocean.on_start(event_listener=EventListenerType.WEBHOOKS_ONLY)
async def setup_for_active_modes() -> None:
    """Run for all active modes except ONCE"""
    logger.info("KAFKA/POLLING/WEBHOOKS_ONLY mode - full setup")
    await setup_external_services()
```

## Execution Priority

The framework follows this priority order:

1. **Event Listener-Specific Functions** (if any exist for current type)
2. **General Functions** (fallback using `@ocean.on_start()` without parameters)
3. **No Functions** (integration starts successfully)

### Backwards Compatibility

```python
# This general function only runs if no specific functions are defined
@ocean.on_start()
async def on_start() -> None:
    """Legacy startup logic - runs as fallback"""
    logger.info("Starting integration (legacy mode)")
    await setup_credentials()
```

## Complete Example

```python
from port_ocean import EventListenerType, ocean
from loguru import logger

async def setup_credentials() -> None:
    """Setup credentials from integration config"""
    # Common credential setup
    logger.info("Setting up credentials")

async def setup_kafka_consumer() -> None:
    """Setup Kafka consumer for real-time events"""
    base_url = ocean.integration_config.get("base_url")

    if not base_url:
        logger.warning("No base URL provided, skipping Kafka setup")
        return

    # Create Kafka consumer
    logger.info(f"Setting up Kafka consumer for {base_url}")

@ocean.on_start(event_listener=EventListenerType.ONCE)
async def on_start_once() -> None:
    """ONCE mode: credentials only"""
    logger.info("Starting in ONCE mode")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.POLLING)
async def on_start_polling() -> None:
    """POLLING mode: credentials only"""
    logger.info("Starting in POLLING mode")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.KAFKA)
async def on_start_kafka() -> None:
    """KAFKA mode: credentials and Kafka consumer"""
    logger.info("Starting in KAFKA mode")
    await setup_credentials()
    await setup_kafka_consumer()

@ocean.on_start(event_listener=EventListenerType.WEBHOOKS_ONLY)
async def on_start_webhooks_only() -> None:
    """WEBHOOKS_ONLY mode: credentials and webhooks"""
    logger.info("Starting in WEBHOOKS_ONLY mode")
    await setup_credentials()
    # Note: WEBHOOKS_ONLY typically doesn't need additional external setup

# Backwards compatibility fallback
@ocean.on_start()
async def on_start() -> None:
    """Legacy startup logic for any unhandled event listener types"""
    logger.info("Starting integration (legacy mode)")
    await setup_credentials()
```

## Benefits

- **🧹 Cleaner Code**: No manual `if` statements for event listener types
- **🔒 Type Safety**: Using `EventListenerType` enum prevents typos
- **🧪 Better Testing**: Each startup function can be tested independently
- **📈 Maintainability**: Clear separation of concerns
- **🔄 Backwards Compatible**: Existing code continues to work
- **💡 IDE Support**: Autocompletion and error detection

## Migration Guide

1. **Keep existing code** - it continues to work
2. **Add specific handlers gradually** for different event listener types
3. **Remove manual checks** once specific handlers are in place
4. **Use `EventListenerType` enum** for type safety

```python
from port_ocean import EventListenerType, ocean
from loguru import logger

async def setup_credentials() -> None:
    """Setup credentials from integration config"""
    # Common credential setup
    logger.info("Setting up credentials")

async def setup_kafka_consumer() -> None:
    """Setup Kafka consumer for real-time events"""
    base_url = ocean.integration_config.get("base_url")

    if not base_url:
        logger.warning("No base URL provided, skipping Kafka setup")
        return

    # Create Kafka consumer
    logger.info(f"Setting up Kafka consumer for {base_url}")

@ocean.on_start(event_listener=EventListenerType.ONCE)
async def on_start_once() -> None:
    """ONCE mode: credentials only"""
    logger.info("Starting in ONCE mode")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.POLLING)
async def on_start_polling() -> None:
    """POLLING mode: credentials only"""
    logger.info("Starting in POLLING mode")
    await setup_credentials()

@ocean.on_start(event_listener=EventListenerType.KAFKA)
async def on_start_kafka() -> None:
    """KAFKA mode: credentials and Kafka consumer"""
    logger.info("Starting in KAFKA mode")
    await setup_credentials()
    await setup_kafka_consumer()

@ocean.on_start(event_listener=EventListenerType.WEBHOOKS_ONLY)
async def on_start_webhooks_only() -> None:
    """WEBHOOKS_ONLY mode: credentials and webhooks"""
    logger.info("Starting in WEBHOOKS_ONLY mode")
    await setup_credentials()
    # Note: WEBHOOKS_ONLY typically doesn't need additional external setup

# Backwards compatibility fallback
@ocean.on_start()
async def on_start() -> None:
    """Legacy startup logic for any unhandled event listener types"""
    logger.info("Starting integration (legacy mode)")
    await setup_credentials()
```
