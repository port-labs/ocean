"""
Health checker for Ocean integrations.

Polls the /isHealthy route at a configurable interval. After a configurable number
of consecutive failures, logs a message and handles the health check as a failure.
"""

import sys
import time

import httpx
from loguru import logger

from port_ocean.health_checker.config import HealthCheckerSettings


def run_health_checker(settings: HealthCheckerSettings | None = None) -> None:
    """Poll the health endpoint; after consecutive failures exceed threshold, log and exit 1."""
    config = settings or HealthCheckerSettings()
    consecutive_failures = 0

    while True:
        try:
            response = httpx.get(
                config.url,
                timeout=config.timeout_seconds,
            )
            response.raise_for_status()
            consecutive_failures = 0
        except Exception as e:
            consecutive_failures += 1
            if consecutive_failures >= config.failure_threshold:
                logger.error(
                    "Health check failed {} times in a row (url={}). Integration appears unhealthy: {}",
                    config.failure_threshold,
                    config.url,
                    e,
                )
                sys.exit(1)
            logger.warning(
                "Health check failed (attempt {}/{}): {}",
                consecutive_failures,
                config.failure_threshold,
                e,
            )

        time.sleep(config.interval_seconds)
