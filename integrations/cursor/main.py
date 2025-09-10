from enum import StrEnum
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from loguru import logger
from port_ocean.context.ocean import ocean
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE

from client import CursorClient


class ObjectKind(StrEnum):
    TEAM = "team"
    USER = "user"
    DAILY_USAGE = "daily-usage"
    AI_COMMIT = "ai-commit"
    AI_CODE_CHANGE = "ai-code-change"
    USAGE_EVENT = "usage-event"


def create_cursor_client() -> CursorClient:
    """Create and return a Cursor client instance."""
    api_key = ocean.integration_config.get("api_key")
    team_id = ocean.integration_config.get("team_id")
    
    if not api_key:
        raise ValueError("Cursor API key is required")
    if not team_id:
        raise ValueError("Cursor team ID is required")
    
    return CursorClient(api_key=api_key, team_id=team_id)


@ocean.on_resync(ObjectKind.TEAM)
async def on_resync_teams(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync team information."""
    logger.info("Starting team resync")
    cursor_client = create_cursor_client()
    
    try:
        team_info = await cursor_client.get_team_info()
        logger.info(f"Retrieved team info: {team_info.get('name', 'Unknown')}")
        yield [team_info]
    except Exception as e:
        logger.error(f"Failed to fetch team info: {e}")
        raise
    finally:
        await cursor_client.close()


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
    finally:
        await cursor_client.close()


@ocean.on_resync(ObjectKind.DAILY_USAGE)
async def on_resync_daily_usage(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync daily usage metrics."""
    logger.info("Starting daily usage resync")
    cursor_client = create_cursor_client()
    
    try:
        # Get usage data for the last 30 days by default
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        # Check for custom date range in integration config
        config_start_date = ocean.integration_config.get("usage_start_date")
        config_end_date = ocean.integration_config.get("usage_end_date")
        
        if config_start_date:
            start_date = datetime.fromisoformat(config_start_date)
        if config_end_date:
            end_date = datetime.fromisoformat(config_end_date)
        
        logger.info(f"Fetching daily usage from {start_date.date()} to {end_date.date()}")
        
        async for usage_batch in cursor_client.get_daily_usage_data(start_date, end_date):
            logger.info(f"Retrieved batch of {len(usage_batch)} daily usage records")
            
            # Enhance each usage record with metadata
            for usage in usage_batch:
                usage["__integration_type"] = "cursor"
                usage["__sync_timestamp"] = datetime.now().isoformat()
            
            yield usage_batch
            
    except Exception as e:
        logger.error(f"Failed to fetch daily usage: {e}")
        raise
    finally:
        await cursor_client.close()


@ocean.on_resync(ObjectKind.AI_COMMIT)
async def on_resync_ai_commits(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync AI commit metrics."""
    logger.info("Starting AI commits resync")
    cursor_client = create_cursor_client()
    
    try:
        # Get AI commit data for the last 30 days by default
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        # Check for custom date range in integration config
        config_start_date = ocean.integration_config.get("ai_commits_start_date")
        config_end_date = ocean.integration_config.get("ai_commits_end_date")
        
        if config_start_date:
            start_date = datetime.fromisoformat(config_start_date)
        if config_end_date:
            end_date = datetime.fromisoformat(config_end_date)
        
        logger.info(f"Fetching AI commits from {start_date.date()} to {end_date.date()}")
        
        async for commits_batch in cursor_client.get_ai_commit_metrics(start_date, end_date):
            logger.info(f"Retrieved batch of {len(commits_batch)} AI commits")
            
            # Enhance each commit record with metadata
            for commit in commits_batch:
                commit["__integration_type"] = "cursor"
                commit["__sync_timestamp"] = datetime.now().isoformat()
            
            yield commits_batch
            
    except Exception as e:
        logger.error(f"Failed to fetch AI commits: {e}")
        raise
    finally:
        await cursor_client.close()


@ocean.on_resync(ObjectKind.AI_CODE_CHANGE)
async def on_resync_ai_code_changes(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync AI code change metrics."""
    logger.info("Starting AI code changes resync")
    cursor_client = create_cursor_client()
    
    try:
        # Get AI code changes for the last 30 days by default
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        # Check for custom date range in integration config
        config_start_date = ocean.integration_config.get("ai_changes_start_date")
        config_end_date = ocean.integration_config.get("ai_changes_end_date")
        
        if config_start_date:
            start_date = datetime.fromisoformat(config_start_date)
        if config_end_date:
            end_date = datetime.fromisoformat(config_end_date)
        
        logger.info(f"Fetching AI code changes from {start_date.date()} to {end_date.date()}")
        
        async for changes_batch in cursor_client.get_ai_code_changes(start_date, end_date):
            logger.info(f"Retrieved batch of {len(changes_batch)} AI code changes")
            
            # Enhance each change record with metadata
            for change in changes_batch:
                change["__integration_type"] = "cursor"
                change["__sync_timestamp"] = datetime.now().isoformat()
            
            yield changes_batch
            
    except Exception as e:
        logger.error(f"Failed to fetch AI code changes: {e}")
        raise
    finally:
        await cursor_client.close()


@ocean.on_resync(ObjectKind.USAGE_EVENT)
async def on_resync_usage_events(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    """Sync usage events."""
    logger.info("Starting usage events resync")
    cursor_client = create_cursor_client()
    
    try:
        # Get usage events for the last 7 days by default
        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()
        
        # Check for custom date range and user filter in integration config
        config_start_date = ocean.integration_config.get("events_start_date")
        config_end_date = ocean.integration_config.get("events_end_date")
        user_email = ocean.integration_config.get("filter_user_email")
        
        if config_start_date:
            start_date = datetime.fromisoformat(config_start_date)
        if config_end_date:
            end_date = datetime.fromisoformat(config_end_date)
        
        logger.info(f"Fetching usage events from {start_date.date()} to {end_date.date()}")
        if user_email:
            logger.info(f"Filtering events for user: {user_email}")
        
        async for events_batch in cursor_client.get_filtered_usage_events(
            start_date, end_date, user_email
        ):
            logger.info(f"Retrieved batch of {len(events_batch)} usage events")
            
            # Enhance each event record with metadata
            for event in events_batch:
                event["__integration_type"] = "cursor"
                event["__sync_timestamp"] = datetime.now().isoformat()
            
            yield events_batch
            
    except Exception as e:
        logger.error(f"Failed to fetch usage events: {e}")
        raise
    finally:
        await cursor_client.close()


@ocean.on_start()
async def on_start() -> None:
    """Integration startup handler."""
    logger.info("Starting Cursor integration")
    
    # Validate required configuration
    api_key = ocean.integration_config.get("api_key")
    team_id = ocean.integration_config.get("team_id")
    
    if not api_key:
        logger.error("Cursor API key is required but not configured")
        raise ValueError("api_key configuration is required")
    
    if not team_id:
        logger.error("Cursor team ID is required but not configured")
        raise ValueError("team_id configuration is required")
    
    logger.info(f"Cursor integration configured for team: {team_id}")


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
        
        start_date = datetime.now() - timedelta(days=30)
        end_date = datetime.now()
        
        for user_email in target_users:
            logger.info(f"Fetching usage for user: {user_email}")
            
            async for usage_batch in cursor_client.get_user_daily_usage(
                user_email, start_date, end_date
            ):
                logger.info(f"Retrieved batch of {len(usage_batch)} usage records for {user_email}")
                
                # Enhance each usage record with metadata
                for usage in usage_batch:
                    usage["__user_email"] = user_email
                    usage["__integration_type"] = "cursor"
                    usage["__sync_timestamp"] = datetime.now().isoformat()
                
                yield usage_batch
                
    except Exception as e:
        logger.error(f"Failed to fetch user daily usage: {e}")
        raise
    finally:
        await cursor_client.close()