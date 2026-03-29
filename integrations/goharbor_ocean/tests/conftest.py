"""Test configuration and Port Ocean stubs."""

from __future__ import annotations

import sys
import types
from typing import Any, AsyncGenerator, Dict, List


def _ensure_module(name: str) -> types.ModuleType:
    """Create or get existing module."""
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


# Create stub package hierarchy for port_ocean
_ensure_module("port_ocean")
_ensure_module("port_ocean.core")

# ocean_types
ocean_types = _ensure_module("port_ocean.core.ocean_types")
RAW_ITEM = Dict[str, Any]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncGenerator[List[RAW_ITEM], None]
setattr(ocean_types, "RAW_ITEM", RAW_ITEM)
setattr(ocean_types, "ASYNC_GENERATOR_RESYNC_TYPE", ASYNC_GENERATOR_RESYNC_TYPE)

# context.ocean stub
context_pkg = _ensure_module("port_ocean.context")
ocean_module = _ensure_module("port_ocean.context.ocean")
ocean = types.SimpleNamespace(
    integration_config={},
    app=types.SimpleNamespace(base_url="https://test.ocean.com"),
    event_listener_type="ALWAYS",
)
setattr(ocean_module, "ocean", ocean)

# context.event stub
event_module = _ensure_module("port_ocean.context.event")
event = types.SimpleNamespace(resource_config=None)
setattr(event_module, "event", event)

# utils.http_async_client stub
utils_module = _ensure_module("port_ocean.utils")
http_async_client = types.SimpleNamespace()
setattr(http_async_client, "request", None)
setattr(utils_module, "http_async_client", http_async_client)

# Webhook handler stubs
handlers_pkg = _ensure_module("port_ocean.core.handlers")
webhook_pkg = _ensure_module("port_ocean.core.handlers.webhook")
webhook_handler = _ensure_module("port_ocean.core.handlers.webhook.webhook_handler")


def register_webhook_processor(path: str, processor: Any) -> None:
    """Stub for webhook processor registration."""
    pass


setattr(webhook_handler, "register_webhook_processor", register_webhook_processor)

# Webhook processor stubs
abstract_processor = _ensure_module("port_ocean.core.handlers.webhook.abstract_webhook_processor")


class AbstractWebhookProcessor:
    """Stub for AbstractWebhookProcessor."""

    pass


setattr(abstract_processor, "AbstractWebhookProcessor", AbstractWebhookProcessor)

# Webhook event stubs
webhook_event_module = _ensure_module("port_ocean.core.handlers.webhook.webhook_event")
EventPayload = Dict[str, Any]
setattr(webhook_event_module, "EventPayload", EventPayload)


class WebhookEvent:
    """Stub for WebhookEvent."""

    def __init__(self, payload: Dict[str, Any], headers: Dict[str, Any]) -> None:
        self.payload = payload
        self.headers = headers


setattr(webhook_event_module, "WebhookEvent", WebhookEvent)


class WebhookEventRawResults:
    """Stub for WebhookEventRawResults."""

    def __init__(
        self,
        updated_raw_results: List[Dict[str, Any]],
        deleted_raw_results: List[Dict[str, Any]],
    ) -> None:
        self.updated_raw_results = updated_raw_results
        self.deleted_raw_results = deleted_raw_results


setattr(webhook_event_module, "WebhookEventRawResults", WebhookEventRawResults)

# Port app config stubs
port_app_config_pkg = _ensure_module("port_ocean.core.handlers.port_app_config")
models_module = _ensure_module("port_ocean.core.handlers.port_app_config.models")


class ResourceConfig:
    """Stub for ResourceConfig."""

    pass


setattr(models_module, "ResourceConfig", ResourceConfig)

# Exception stubs
exceptions_module = _ensure_module("port_ocean.exceptions.core")


class OceanAbortException(Exception):
    """Stub for OceanAbortException."""

    pass


setattr(exceptions_module, "OceanAbortException", OceanAbortException)
