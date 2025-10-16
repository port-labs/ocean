"""Simple Harbor webhook configuration helper."""

from typing import List
from loguru import logger
from port_ocean.context.ocean import ocean


def log_harbor_webhook_config(base_url: str, webhook_events: List[str]) -> None:
    """Log Harbor webhook configuration instructions."""

    webhook_url = f"{base_url}/integration/webhook"
    webhook_secret = ocean.integration_config.get("webhook_secret")

    logger.info("=" * 60)
    logger.info("HARBOR WEBHOOK CONFIGURATION")
    logger.info("=" * 60)
    logger.info(f"Webhook endpoint: {webhook_url}")
    logger.info(f"Event types: {', '.join(webhook_events)}")
    if webhook_secret:
        logger.debug(f"   - Auth Header: {webhook_secret[:10]}...")
    else:
        logger.debug("   - Auth Header: (not configured)")
    logger.info("   - Skip Certificate Verification: ✅ (for development)")
    logger.info("=" * 60)
