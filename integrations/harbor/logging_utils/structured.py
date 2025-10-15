"""Structured logging utilities for Harbor integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from loguru import logger

LOG_LEVELS = {"DEBUG", "INFO", "WARN", "WARNING", "ERROR"}


def configure_harbor_logger(level: str | None) -> None:
    """Configure loguru with the requested level if provided."""

    if not level:
        return
    normalized = level.upper()
    if normalized == "WARN":
        normalized = "WARNING"
    if normalized not in LOG_LEVELS:
        logger.warning("Unknown log level provided for Harbor integration", level=level)
        return
    logger.remove()
    logger.add(lambda msg: print(msg, end=""), level=normalized)


@dataclass
class HarborLogContext:
    """Aggregation structure for resync summaries and metrics."""

    updated: int = 0
    deleted: int = 0
    errors: int = 0
    by_kind: dict[str, dict[str, int]] = field(default_factory=dict)

    def track(self, kind: str, *, updated: int = 0, deleted: int = 0, errors: int = 0) -> None:
        group = self.by_kind.setdefault(kind, {"updated": 0, "deleted": 0, "errors": 0})
        group["updated"] += updated
        group["deleted"] += deleted
        group["errors"] += errors
        self.updated += updated
        self.deleted += deleted
        self.errors += errors


def with_org_context(
    base: Mapping[str, Any] | None = None, *, organization_id: str | None = None
) -> dict[str, Any]:
    """Return a new mapping enriched with the organization identifier if provided."""

    enriched = dict(base or {})
    if organization_id:
        enriched["organization_id"] = organization_id
    return enriched


def log_webhook_event(
    event_type: str,
    *,
    updated: int,
    deleted: int,
    verified: bool,
    organization_id: str | None = None,
) -> None:
    extra = with_org_context(
        {
            "event_type": event_type,
            "updated_count": updated,
            "deleted_count": deleted,
            "verified": verified,
        },
        organization_id=organization_id,
    )

    logger.info("harbor.webhook.processed", **extra)


def log_resync_summary(
    context: HarborLogContext,
    *,
    organization_id: str | None = None,
) -> None:
    summary_rows = [
        {
            "kind": kind,
            "updated": stats["updated"],
            "deleted": stats["deleted"],
            "errors": stats["errors"],
        }
        for kind, stats in context.by_kind.items()
    ]

    payload = with_org_context(
        {
            "totals": {
                "updated": context.updated,
                "deleted": context.deleted,
                "errors": context.errors,
            },
            "details": summary_rows,
        },
        organization_id=organization_id,
    )

    logger.info("harbor.resync.summary", **payload)
