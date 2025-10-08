from __future__ import annotations

import sys
import types
from typing import Any, AsyncGenerator, Dict, List


def _ensure_module(name: str) -> types.ModuleType:
    if name in sys.modules:
        return sys.modules[name]
    module = types.ModuleType(name)
    sys.modules[name] = module
    return module


# Create stub package hierarchy for port_ocean used by tests (minimal)
_ensure_module("port_ocean")
_ensure_module("port_ocean.core")

# ocean_types
ocean_types = _ensure_module("port_ocean.core.ocean_types")
RAW_ITEM = Dict[str, Any]
ASYNC_GENERATOR_RESYNC_TYPE = AsyncGenerator[List[RAW_ITEM], None]
setattr(ocean_types, "RAW_ITEM", RAW_ITEM)
setattr(ocean_types, "ASYNC_GENERATOR_RESYNC_TYPE", ASYNC_GENERATOR_RESYNC_TYPE)

# context.ocean stub (used by client factory)
context_pkg = _ensure_module("port_ocean.context")
ocean_module = _ensure_module("port_ocean.context.ocean")
ocean = types.SimpleNamespace(integration_config={})
setattr(ocean_module, "ocean", ocean)

# utils.http_async_client stub so code can import and tests can patch its request
utils_module = _ensure_module("port_ocean.utils")
http_async_client = types.SimpleNamespace()
# Provide a placeholder attribute so patching works
setattr(http_async_client, "request", None)
setattr(utils_module, "http_async_client", http_async_client)
