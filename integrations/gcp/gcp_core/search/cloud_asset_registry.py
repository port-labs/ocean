"""Registry of Cloud Asset APIs that are not searchAllResources.

To add an API:

1. Add a module with its selector, ``ResourceConfig``, raw validator, and fetcher.
2. Call ``register`` and import that module from ``load_cloud_asset_apis``.
3. Add the config class to ``GCPPortAppConfig.resources`` before
   ``GCPResourceConfig`` so Port can discriminate the kind.

Do not add a branch to the resync handlers. The generic handler calls
``get_api(kind)``.
"""

from collections.abc import Callable
from typing import Any

from port_ocean.core.handlers.port_app_config.models import ResourceConfig
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

CloudAssetFetcher = Callable[[ResourceConfig], ASYNC_GENERATOR_RESYNC_TYPE]
CloudAssetValidator = Callable[[dict[str, Any]], None]


class CloudAssetApi:
    def __init__(
        self,
        kind: str,
        config_cls: type[ResourceConfig],
        fetch: CloudAssetFetcher,
        validate_raw: CloudAssetValidator | None = None,
    ) -> None:
        self.kind = kind
        self.config_cls = config_cls
        self.fetch = fetch
        self.validate_raw = validate_raw


_REGISTRY: dict[str, CloudAssetApi] = {}


def register(api: CloudAssetApi) -> CloudAssetApi:
    existing = _REGISTRY.get(api.kind)
    if existing is not None and existing is not api:
        raise ValueError(f"Cloud Asset API kind {api.kind!r} is already registered")
    _REGISTRY[api.kind] = api
    return api


def get_api(kind: str) -> CloudAssetApi | None:
    return _REGISTRY.get(kind)


def registered_config_classes() -> tuple[type[ResourceConfig], ...]:
    return tuple(api.config_cls for api in _REGISTRY.values())


def validate_registered_resources(values: dict[str, Any]) -> None:
    """Run each API's raw-config check before the generic kind can swallow it."""
    resources = values.get("resources") or []
    if not isinstance(resources, list):
        return
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        kind = resource.get("kind")
        if not isinstance(kind, str):
            continue
        api = _REGISTRY.get(kind)
        if api is not None and api.validate_raw is not None:
            api.validate_raw(resource)


def load_cloud_asset_apis() -> None:
    """Import API modules for their ``register`` side effect."""
    import gcp_core.search.iam_policies  # noqa: F401
