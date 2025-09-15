from __future__ import annotations

from typing import Any, AsyncGenerator, Dict, Iterable, List

from loguru import logger
from port_ocean.context.ocean import ocean

from . import mapping
from .client import SailPointClient
from .config import SailPointConfig
from .exporters.access_profiles import AccessProfilesExporter
from .exporters.accounts import AccountsExporter
from .exporters.entitlements import EntitlementsExporter
from .exporters.identities import IdentitiesExporter
from .exporters.roles import RolesExporter
from .exporters.sources import SourcesExporter

print(">>> SAILPOINT INTEGRATION MODULE LOADED")

# --------------------------------------------------------------------------------------
# Lazily build client/config exactly when Ocean calls us (no access at module import)
# --------------------------------------------------------------------------------------
_cfg: SailPointConfig | None = None
_client: SailPointClient | None = None


def _ensure_client() -> SailPointClient:
    global _cfg, _client
    if _client is None:
        # At this point Ocean is fully initialized; ocean.config is available
        _cfg = SailPointConfig.parse_obj(ocean.config)
        _client = SailPointClient(_cfg)
        logger.info(
            "[sailpoint] Client initialized (tenant=%s)",
            getattr(_cfg, "tenant", "<unknown>"),
        )
    return _client


def _exporters() -> List[Any]:
    """
    Build exporter instances (sharing the same client/config).
    Each exporter implements: async def ingest(ocean) -> Iterable[dict] | AsyncGenerator[dict, None]
    """
    client = _ensure_client()
    return [
        IdentitiesExporter(client, mapping=mapping, cfg=_cfg),
        AccountsExporter(client, mapping=mapping, cfg=_cfg),
        EntitlementsExporter(client, mapping=mapping, cfg=_cfg),
        AccessProfilesExporter(client, mapping=mapping, cfg=_cfg),
        RolesExporter(client, mapping=mapping, cfg=_cfg),
        SourcesExporter(client, mapping=mapping, cfg=_cfg),
    ]


# --------------------------------------------------------------------------------------
# Health & Manual endpoints — mounted directly via ocean.router (per Ocean docs)
#   GET  /sailpoint/ping   -> {"pong": true}
#   POST /sailpoint/resync -> triggers full raw resync (all @ocean.on_resync handlers)
# --------------------------------------------------------------------------------------


@ocean.router.get("/integration/sailpoint/ping")
@ocean.router.get("/sailpoint/ping")
def ping() -> Dict[str, bool]:
    """Simple liveness check."""
    return {"pong": True}


@ocean.router.post("/integration/sailpoint/resync")
@ocean.router.post("/sailpoint/resync")
async def manual_resync() -> Dict[str, bool]:
    """
    Trigger a full raw sync (calls all @ocean.on_resync handlers).
    Synchronous per Ocean docs: https://ocean.getport.io/framework/features/sync/  (ocean.sync_raw_all)
    """
    logger.info("[sailpoint] Manual resync requested via HTTP")
    await ocean.sync_raw_all()
    return {"ok": True}


# --------------------------------------------------------------------------------------
# Resync producers
#   The framework will call these when:
#     - the polling listener detects changes,
#     - a resync is triggered from Port,
#     - or our /sailpoint/resync endpoint above is hit.
#
#   Return / yield RAW objects (dicts). Mapping is applied by Ocean using your resources mapping.
#   You can split per-kind with @ocean.on_resync("KindName"), or keep one generic.
# --------------------------------------------------------------------------------------


@ocean.on_resync()  # generic handler: Ocean will invoke this for each mapped "kind"
async def on_resync(kind: str) -> List[Dict[str, Any]]:
    """
    Generic resync: when Ocean asks for <kind>, return a list of raw dicts from the matching exporter.
    This avoids blocking and plays nicely with large catalogs.
    """
    logger.info("[sailpoint] on_resync(kind=%s) started", kind)

    kind_to_exporter_name = {
        "sailpoint-identities": IdentitiesExporter,
        "sailpoint-accounts": AccountsExporter,
        "sailpoint-entitlements": EntitlementsExporter,
        "sailpoint-access-profiles": AccessProfilesExporter,
        "sailpoint-roles": RolesExporter,
        "sailpoint-sources": SourcesExporter,
    }

    ExporterCls = kind_to_exporter_name.get(kind)
    if ExporterCls is None:
        logger.debug(
            "[sailpoint] on_resync(kind=%s) no matching exporter, skipping", kind
        )
        return []

    client = _ensure_client()
    exporter = ExporterCls(client, mapping=mapping, cfg=_cfg)

    # Collect all items into a list and return
    items = []
    async for item in _aiter(exporter.ingest(ocean)):
        items.append(item)

    logger.info("[sailpoint] on_resync(kind=%s) finished", kind)
    return items


# --------------------------------------------------------------------------------------
# Small helper to normalize either async gen or async fn -> async gen
# --------------------------------------------------------------------------------------


async def _aiter(data: Any) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Accepts:
      - async generator yielding dicts
      - awaitable returning Iterable[dict]
    Yields dict rows either way.
    """
    # async generator
    if hasattr(data, "__anext__"):
        async for row in data:
            yield row
        return

    # awaitable returning iterable
    if hasattr(data, "__await__"):
        res = await data  # type: ignore[func-returns-value]
        if isinstance(res, dict):
            yield res
        elif isinstance(res, Iterable):
            for row in res:
                yield row  # type: ignore[misc]
        return

    # plain iterable (shouldn't usually happen, but be defensive)
    if isinstance(data, dict):
        yield data
    elif isinstance(data, Iterable):
        for row in data:
            yield row  # type: ignore[misc]
