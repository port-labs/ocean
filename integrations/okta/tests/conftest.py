"""Test configuration: Provide lightweight stubs for port_ocean to avoid heavy imports.

This avoids ModuleNotFoundError for older/newer port_ocean layouts when running integration-local tests.
"""

from __future__ import annotations

import sys
import types
from typing import Any, AsyncGenerator, Dict, List, Optional
from pydantic import BaseModel


def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


# Create stub package hierarchy for port_ocean used by tests
port_ocean = _ensure_module("port_ocean")
port_ocean_core = _ensure_module("port_ocean.core")

# ocean_types
ocean_types = _ensure_module("port_ocean.core.ocean_types")
RAW_ITEM = Dict[str, Any]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncGenerator[List[RAW_ITEM], None]
setattr(ocean_types, "RAW_ITEM", RAW_ITEM)
setattr(ocean_types, "ASYNC_GENERATOR_RESYNC_TYPE", ASYNC_GENERATOR_RESYNC_TYPE)

# handlers.webhook.webhook_event
handlers = _ensure_module("port_ocean.core.handlers")
handlers_webhook = _ensure_module("port_ocean.core.handlers.webhook")
webhook_event = _ensure_module("port_ocean.core.handlers.webhook.webhook_event")


class WebhookEvent:
    def __init__(self, trace_id: str, payload: Dict[str, Any], headers: Dict[str, Any]):
        self.trace_id = trace_id
        self.payload = payload
        self.headers = headers


EventPayload = Dict[str, Any]


class WebhookEventRawResults:
    def __init__(
        self,
        updated_raw_results: Optional[List[Dict[str, Any]]] = None,
        deleted_raw_results: Optional[List[Dict[str, Any]]] = None,
    ):
        self.updated_raw_results = updated_raw_results or []
        self.deleted_raw_results = deleted_raw_results or []


setattr(webhook_event, "WebhookEvent", WebhookEvent)
setattr(webhook_event, "EventPayload", EventPayload)
setattr(webhook_event, "WebhookEventRawResults", WebhookEventRawResults)
setattr(webhook_event, "EventHeaders", Dict[str, Any])

# handlers.port_app_config.models
handlers_port_app_config = _ensure_module("port_ocean.core.handlers.port_app_config")
models = _ensure_module("port_ocean.core.handlers.port_app_config.models")


class Selector(BaseModel):
    """Pydantic-based Selector stub to support Field arguments in tests."""


class ResourceConfig:
    def __init__(
        self, kind: str, selector: Any | None = None, port: Any | None = None
    ):  # noqa: A003
        self.kind = kind
        self.selector = selector
        self.port = port


class PortAppConfig:
    def __init__(self, resources: List[Any]):
        self.resources = resources


setattr(models, "Selector", Selector)
setattr(models, "ResourceConfig", ResourceConfig)
setattr(models, "PortAppConfig", PortAppConfig)

# handlers.webhook.abstract_webhook_processor (minimal stub)
abstract_webhook_pkg = _ensure_module(
    "port_ocean.core.handlers.webhook.abstract_webhook_processor"
)


class AbstractWebhookProcessor:  # minimal interface for tests
    async def authenticate(
        self, payload: Dict[str, Any], headers: Dict[str, Any]
    ) -> bool:  # noqa: D401
        return True

    async def validate_payload(self, payload: Dict[str, Any]) -> bool:  # noqa: D401
        return True


setattr(abstract_webhook_pkg, "AbstractWebhookProcessor", AbstractWebhookProcessor)

# core.integrations.base (minimal stub)
core_integrations_base = _ensure_module("port_ocean.core.integrations.base")


class BaseIntegration:  # minimal stub
    pass


setattr(core_integrations_base, "BaseIntegration", BaseIntegration)

# handlers.port_app_config.api (minimal stub)
api_module = _ensure_module("port_ocean.core.handlers.port_app_config.api")


class APIPortAppConfig:  # minimal stub
    pass


setattr(api_module, "APIPortAppConfig", APIPortAppConfig)

# context.ocean stub
context_pkg = _ensure_module("port_ocean.context")
ocean_module = _ensure_module("port_ocean.context.ocean")
ocean = types.SimpleNamespace(integration_config={})
setattr(ocean_module, "ocean", ocean)
