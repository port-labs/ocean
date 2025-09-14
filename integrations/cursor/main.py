from enum import StrEnum
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import CursorClient


class ObjectKind(StrEnum):
    USER = "user"
    DAILY_USAGE = "daily-usage"
    USAGE_EVENT = "usage-event"
    BLOCKLISTED_REPO = "blocklisted-repo"
    SPENDING_DATA = "spending-data"
    AI_COMMIT_METRICS = "ai-commit-metrics"
    AI_CODE_CHANGE_METRICS = "ai-code-change-metrics"


def create_cursor_client() -> CursorClient:
    """Create and return a Cursor client instance."""
    api_key = ocean.integration_config.get("api_key")

    if not api_key:
        raise ValueError("Cursor API key is required")

    return CursorClient(api_key=api_key)


@ocean.on_resync(ObjectKind.USER)
async def on_resync_users(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync team members."""
    logger.info("Starting users resync")
    cursor_client = create_cursor_client()

    try:
        members = await cursor_client.get_team_members()
        logger.info(f"Retrieved {len(members)} team members")

        for member in members:
            logger.debug(f"Processing member: {member.get('email', 'Unknown')}")

        yield members
    except Exception as e:
        logger.error(f"Failed to fetch team members: {e}")
        raise


@ocean.on_resync(ObjectKind.DAILY_USAGE)
async def on_resync_daily_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync daily usage metrics."""
    logger.info("Starting daily usage resync")
    cursor_client = create_cursor_client()

    try:
        # Get usage data for the configured number of days back
        lookback_days = ocean.integration_config.get("usage_lookback_days", 30)
        start_date = datetime.now() - timedelta(days=lookback_days)
        end_date = datetime.now()

        logger.info(
            f"Fetching daily usage for the last {lookback_days} days (from {start_date.date()} to {end_date.date()})"
        )

        async for usage_batch in cursor_client.get_daily_usage_data(
            start_date, end_date
        ):
            logger.info(f"Retrieved batch of {len(usage_batch)} daily usage records")
            yield usage_batch

    except Exception as e:
        logger.error(f"Failed to fetch daily usage: {e}")
        raise


@ocean.on_resync(ObjectKind.USAGE_EVENT)
async def on_resync_usage_events(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync usage events."""
    logger.info("Starting usage events resync")
    cursor_client = create_cursor_client()

    try:
        lookback_days = ocean.integration_config.get("events_lookback_days", 7)
        start_date = datetime.now() - timedelta(days=lookback_days)
        end_date = datetime.now()
        logger.info(
            f"Fetching usage events for the last {lookback_days} days (from {start_date.date()} to {end_date.date()})"
        )

        async for events_batch in cursor_client.get_filtered_usage_events(
            start_date, end_date
        ):
            logger.info(f"Retrieved batch of {len(events_batch)} usage events")
            yield events_batch

    except Exception as e:
        logger.error(f"Failed to fetch usage events: {e}")
        raise


@ocean.on_start()
async def on_start() -> None:
    """Integration startup handler."""
    logger.info("Starting Cursor integration")

    # Validate required configuration
    api_key = ocean.integration_config.get("api_key")

    if not api_key:
        logger.error("Cursor API key is required but not configured")
        raise ValueError("api_key configuration is required")

    logger.info("Cursor integration configured successfully")


# Optional: Handle specific user usage if needed
@ocean.on_resync("user-daily-usage")
async def on_resync_user_daily_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync daily usage for specific users."""
    logger.info("Starting user daily usage resync")
    cursor_client = create_cursor_client()

    try:
        # Get list of users to fetch usage for
        target_users = ocean.integration_config.get("target_users", [])

        if not target_users:
            logger.warning("No target users specified for user daily usage sync")
            return

        # Get usage data for the configured number of days back
        lookback_days = ocean.integration_config.get("usage_lookback_days", 30)
        start_date = datetime.now() - timedelta(days=lookback_days)
        end_date = datetime.now()

        logger.info(
            f"Fetching user daily usage for the last {lookback_days} days (from {start_date.date()} to {end_date.date()})"
        )

        for user_email in target_users:
            logger.info(f"Fetching usage for user: {user_email}")

            async for usage_batch in cursor_client.get_filtered_user_usage(
                start_date, end_date
            ):
                logger.info(
                    f"Retrieved batch of {len(usage_batch)} usage records for {user_email}"
                )
                yield usage_batch

    except Exception as e:
        logger.error(f"Failed to fetch user daily usage: {e}")
        raise


@ocean.on_resync(ObjectKind.BLOCKLISTED_REPO)
async def on_resync_blocklisted_repos(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync blocklisted repositories."""
    logger.info("Starting blocklisted repos resync")
    cursor_client = create_cursor_client()

    try:
        blocklisted_repos = await cursor_client.get_blocklisted_repos()
        logger.info(f"Retrieved {len(blocklisted_repos)} blocklisted repositories")
        yield blocklisted_repos

    except Exception as e:
        logger.error(f"Failed to fetch blocklisted repos: {e}")
        raise


@ocean.on_resync(ObjectKind.SPENDING_DATA)
async def on_resync_spending_data(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync spending data."""
    logger.info("Starting spending data resync")
    cursor_client = create_cursor_client()

    try:
        # Get spending data for the configured number of days back
        lookback_days = ocean.integration_config.get("spending_lookback_days", 30)
        start_date = datetime.now() - timedelta(days=lookback_days)
        end_date = datetime.now()

        logger.info(
            f"Fetching spending data for the last {lookback_days} days (from {start_date.date()} to {end_date.date()})"
        )

        spending_data = await cursor_client.get_spending_data(start_date, end_date)
        logger.info(f"Retrieved spending data: {spending_data}")

        if isinstance(spending_data, dict):
            yield [spending_data]
        elif isinstance(spending_data, list):
            yield spending_data
        else:
            yield []

    except Exception as e:
        logger.error(f"Failed to fetch spending data: {e}")
        raise


@ocean.on_resync(ObjectKind.AI_COMMIT_METRICS)
async def on_resync_ai_commit_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync AI commit metrics."""
    logger.info("Starting AI commit metrics resync")
    cursor_client = create_cursor_client()

    try:
        lookback_days = ocean.integration_config.get("ai_metrics_lookback_days", 7)
        start_date = datetime.now() - timedelta(days=lookback_days)
        end_date = datetime.now()

        logger.info(
            f"Fetching AI commit metrics for the last {lookback_days} days (from {start_date.date()} to {end_date.date()})"
        )r.info(f"Filtering metrics for user: {user_filter}")

        async for metrics_batch in cursor_client.get_ai_commit_metrics(
            start_date, end_date,
        ):
            logger.info(f"Retrieved batch of {len(metrics_batch)} AI commit metrics")
            yield metrics_batch

    except Exception as e:
        logger.error(f"Failed to fetch AI commit metrics: {e}")
        raise


@ocean.on_resync(ObjectKind.AI_CODE_CHANGE_METRICS)
async def on_resync_ai_code_change_metrics(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync AI code change metrics."""
    logger.info("Starting AI code change metrics resync")
    cursor_client = create_cursor_client()

    try:
        # Get AI code change metrics for the configured number of days back
        lookback_days = ocean.integration_config.get("ai_metrics_lookback_days", 7)
        start_date = datetime.now() - timedelta(days=lookback_days)
        end_date = datetime.now()

        # Check for user filter in integration config
        user_filter = ocean.integration_config.get("filter_user_email")

        logger.info(
            f"Fetching AI code change metrics for the last {lookback_days} days (from {start_date.date()} to {end_date.date()})"
        )
        if user_filter:
            logger.info(f"Filtering metrics for user: {user_filter}")

        async for metrics_batch in cursor_client.get_ai_code_change_metrics(
            start_date, end_date, user=user_filter
        ):
            logger.info(
                f"Retrieved batch of {len(metrics_batch)} AI code change metrics"
            )
            yield metrics_batch

    except Exception as e:
        logger.error(f"Failed to fetch AI code change metrics: {e}")
        raise
