import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime

from main import (
    create_cursor_client,
    on_resync_teams,
    on_resync_users, 
    on_resync_daily_usage,
    on_resync_ai_commits,
    on_resync_usage_events,
    on_start
)


@pytest.mark.asyncio
async def test_create_cursor_client_success(mock_ocean_context):
    """Test successful creation of CursorClient."""
    with patch("main.CursorClient") as mock_client_class:
        mock_client = AsyncMock()
        mock_client_class.return_value = mock_client
        
        client = create_cursor_client()
        
        mock_client_class.assert_called_once_with(
            api_key="test-api-key",
            team_id="test-team-id"
        )
        assert client == mock_client


@pytest.mark.asyncio
async def test_create_cursor_client_missing_api_key(mock_ocean_context):
    """Test CursorClient creation with missing API key."""
    mock_ocean_context.integration_config = {"team_id": "test-team-id"}
    
    with pytest.raises(ValueError, match="Cursor API key is required"):
        create_cursor_client()


@pytest.mark.asyncio
async def test_create_cursor_client_missing_team_id(mock_ocean_context):
    """Test CursorClient creation with missing team ID."""
    mock_ocean_context.integration_config = {"api_key": "test-api-key"}
    
    with pytest.raises(ValueError, match="Cursor team ID is required"):
        create_cursor_client()


@pytest.mark.asyncio
async def test_on_resync_teams_success(mock_ocean_context, sample_team_data):
    """Test successful team resync."""
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_team_info.return_value = sample_team_data
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_teams("team"):
            result.extend(batch)
        
        assert len(result) == 1
        assert result[0] == sample_team_data
        mock_client.get_team_info.assert_called_once()
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_on_resync_users_success(mock_ocean_context, sample_user_data):
    """Test successful users resync."""
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_team_members.return_value = sample_user_data
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_users("user"):
            result.extend(batch)
        
        assert len(result) == 2
        assert result == sample_user_data
        mock_client.get_team_members.assert_called_once()
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_on_resync_daily_usage_success(mock_ocean_context, sample_daily_usage_data):
    """Test successful daily usage resync."""
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        
        async def mock_get_daily_usage_data(start_date, end_date):
            yield sample_daily_usage_data
        
        mock_client.get_daily_usage_data = mock_get_daily_usage_data
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_daily_usage("daily-usage"):
            result.extend(batch)
        
        assert len(result) == 2
        # Check that metadata was added
        for item in result:
            assert "__integration_type" in item
            assert "__sync_timestamp" in item
            assert item["__integration_type"] == "cursor"
        
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_on_resync_ai_commits_success(mock_ocean_context, sample_ai_commit_data):
    """Test successful AI commits resync."""
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        
        async def mock_get_ai_commit_metrics(start_date, end_date):
            yield sample_ai_commit_data
        
        mock_client.get_ai_commit_metrics = mock_get_ai_commit_metrics
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_ai_commits("ai-commit"):
            result.extend(batch)
        
        assert len(result) == 1
        assert result[0]["commit_hash"] == "abc123def456"
        # Check that metadata was added
        assert "__integration_type" in result[0]
        assert "__sync_timestamp" in result[0]
        
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_on_resync_usage_events_success(mock_ocean_context, sample_usage_events_data):
    """Test successful usage events resync.""" 
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        
        async def mock_get_filtered_usage_events(start_date, end_date, user_email):
            yield sample_usage_events_data
        
        mock_client.get_filtered_usage_events = mock_get_filtered_usage_events
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_usage_events("usage-event"):
            result.extend(batch)
        
        assert len(result) == 2
        # Check that metadata was added
        for item in result:
            assert "__integration_type" in item
            assert "__sync_timestamp" in item
        
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_on_resync_with_custom_dates(mock_ocean_context, sample_daily_usage_data):
    """Test resync with custom date configuration."""
    mock_ocean_context.integration_config.update({
        "usage_start_date": "2024-01-01T00:00:00",
        "usage_end_date": "2024-01-31T23:59:59"
    })
    
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        
        async def mock_get_daily_usage_data(start_date, end_date):
            # Verify the dates are parsed correctly
            assert start_date.year == 2024
            assert start_date.month == 1
            assert start_date.day == 1
            assert end_date.year == 2024
            assert end_date.month == 1
            assert end_date.day == 31
            yield sample_daily_usage_data
        
        mock_client.get_daily_usage_data = mock_get_daily_usage_data
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_daily_usage("daily-usage"):
            result.extend(batch)
        
        assert len(result) == 2
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_on_start_success(mock_ocean_context):
    """Test successful integration startup."""
    await on_start()
    # Should complete without errors


@pytest.mark.asyncio
async def test_on_start_missing_config(mock_ocean_context):
    """Test integration startup with missing configuration."""
    mock_ocean_context.integration_config = {}
    
    with pytest.raises(ValueError, match="api_key configuration is required"):
        await on_start()


@pytest.mark.asyncio
async def test_resync_error_handling(mock_ocean_context):
    """Test error handling during resync operations."""
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        mock_client.get_team_info.side_effect = Exception("API Error")
        mock_create_client.return_value = mock_client
        
        with pytest.raises(Exception, match="API Error"):
            async for _ in on_resync_teams("team"):
                pass
        
        # Ensure client is still closed even on error
        mock_client.close.assert_called_once()


@pytest.mark.asyncio
async def test_filtered_usage_events_with_user_email(mock_ocean_context, sample_usage_events_data):
    """Test usage events resync with user email filter."""
    mock_ocean_context.integration_config["filter_user_email"] = "user1@example.com"
    
    with patch("main.create_cursor_client") as mock_create_client:
        mock_client = AsyncMock()
        
        async def mock_get_filtered_usage_events(start_date, end_date, user_email):
            assert user_email == "user1@example.com"
            yield sample_usage_events_data
        
        mock_client.get_filtered_usage_events = mock_get_filtered_usage_events
        mock_create_client.return_value = mock_client
        
        result = []
        async for batch in on_resync_usage_events("usage-event"):
            result.extend(batch)
        
        assert len(result) == 2
        mock_client.close.assert_called_once()