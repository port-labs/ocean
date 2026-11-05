from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger
from port_ocean.context.ocean import ocean


@dataclass(frozen=True)
class QuotaCheckResult:
    allowed: bool
    message: str | None = None


class FoundryQuotaClient:
    """Lightweight quota guard before expensive sync/action batches.

    When ``enforceQuotaChecks`` is enabled, the integration reads optional
    ``quotaLimits`` from integration config (per-region hosted session caps).
    Full Azure Quota API integration can extend this client later.
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._enforce = bool(
            config.get("enforce_quota_checks") or config.get("enforceQuotaChecks")
        )
        limits = config.get("quota_limits") or config.get("quotaLimits") or {}
        self._limits: dict[str, int] = {
            str(region): int(value)
            for region, value in limits.items()
            if isinstance(value, int)
        }

    async def check_before_batch(
        self, *, region: str | None, batch_size: int
    ) -> QuotaCheckResult:
        if not self._enforce:
            return QuotaCheckResult(allowed=True)
        if not region or region not in self._limits:
            return QuotaCheckResult(allowed=True)
        limit = self._limits[region]
        if batch_size > limit:
            message = (
                f"Batch size {batch_size} exceeds configured quota limit "
                f"{limit} for region {region}"
            )
            logger.warning(message)
            return QuotaCheckResult(allowed=False, message=message)
        return QuotaCheckResult(allowed=True)


def create_quota_client() -> FoundryQuotaClient:
    return FoundryQuotaClient(dict(ocean.integration_config))
