import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import httpx

from client import CursorClient


@pytest.fixture
def cursor_client():
    """Create a CursorClient instance for testing."""
    return CursorClient(api_key="test-api-key", team_id="test-team-id")


@pytest.mark.asyncio
async def test_client_initialization(cursor_client):
    """Test that CursorClient initializes correctly."""
    assert cursor_client.api_key == "test-api-key"
    assert cursor_client.team_id == "test-team-id"
    assert cursor_client.BASE_URL == "https://api.cursor.com"


@pytest.mark.asyncio
async def test_get_team_members_success(cursor_client):
    """Test successful retrieval of team members."""
    mock_response = [
        {
            "id": "user1",
            "email": "user1@example.com",
            "name": "User One",
            "role": "admin"
        },
        {
            "id": "user2",
            "email": "user2@example.com",
            "name": "User Two", 
            "role": "member"
        }
    ]
    
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None
        
        result = await cursor_client.get_team_members()
        
        assert result == mock_response
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_team_info_success(cursor_client):
    """Test successful retrieval of team info."""
    mock_response = {
        "id": "test-team-id",
        "name": "Test Team",
        "description": "A test team",
        "member_count": 5,
        "plan_type": "pro"
    }
    
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None
        
        result = await cursor_client.get_team_info()
        
        assert result == mock_response
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_daily_usage_data_success(cursor_client):
    """Test successful retrieval of daily usage data."""
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    mock_response = [
        {
            "date": "2024-01-01",
            "total_active_time_minutes": 240,
            "ai_interactions": 50,
            "lines_generated": 1200
        },
        {
            "date": "2024-01-02", 
            "total_active_time_minutes": 180,
            "ai_interactions": 35,
            "lines_generated": 800
        }
    ]
    
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None
        
        result_batches = []
        async for batch in cursor_client.get_daily_usage_data(start_date, end_date):
            result_batches.append(batch)
        
        assert len(result_batches) == 1
        assert result_batches[0] == mock_response
        mock_get.assert_called_once()


@pytest.mark.asyncio 
async def test_get_ai_commit_metrics_success(cursor_client):
    """Test successful retrieval of AI commit metrics."""
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now()
    
    mock_response = {
        "commits": [
            {
                "commit_hash": "abc123",
                "repository": "test-repo",
                "author_email": "user@example.com",
                "message": "Add new feature",
                "ai_assistance_level": "high"
            }
        ]
    }
    
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None
        
        result_batches = []
        async for batch in cursor_client.get_ai_commit_metrics(start_date, end_date):
            result_batches.append(batch)
        
        assert len(result_batches) == 1
        assert result_batches[0] == mock_response["commits"]
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_get_filtered_usage_events_success(cursor_client):
    """Test successful retrieval of filtered usage events."""
    start_date = datetime.now() - timedelta(days=1)
    end_date = datetime.now()
    user_email = "user@example.com"
    
    mock_response = {
        "events": [
            {
                "event_id": "event1",
                "timestamp": "2024-01-01T10:00:00Z",
                "user_email": user_email,
                "event_type": "ai_interaction"
            }
        ]
    }
    
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.return_value = mock_response
        mock_get.return_value.raise_for_status.return_value = None
        
        result_batches = []
        async for batch in cursor_client.get_filtered_usage_events(start_date, end_date, user_email):
            result_batches.append(batch)
        
        assert len(result_batches) == 1
        assert result_batches[0] == mock_response["events"]
        mock_get.assert_called_once()


@pytest.mark.asyncio
async def test_http_error_handling(cursor_client):
    """Test HTTP error handling."""
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Not Found", request=None, response=AsyncMock(status_code=404, text="Not Found")
        )
        
        with pytest.raises(httpx.HTTPStatusError):
            await cursor_client.get_team_info()


@pytest.mark.asyncio
async def test_pagination_handling(cursor_client):
    """Test pagination handling in API responses."""
    first_response = {
        "data": [{"id": 1}, {"id": 2}],
        "next_page_token": "next_token"
    }
    second_response = {
        "data": [{"id": 3}, {"id": 4}]
    }
    
    with patch.object(cursor_client.client, 'get', new_callable=AsyncMock) as mock_get:
        mock_get.return_value.json.side_effect = [first_response, second_response]
        mock_get.return_value.raise_for_status.return_value = None
        
        result_batches = []
        async for batch in cursor_client.get_daily_usage_data():
            result_batches.append(batch)
        
        assert len(result_batches) == 2
        assert result_batches[0] == first_response["data"]
        assert result_batches[1] == second_response["data"]
        assert mock_get.call_count == 2


@pytest.mark.asyncio
async def test_client_close(cursor_client):
    """Test client cleanup."""
    with patch.object(cursor_client.client, 'close', new_callable=AsyncMock) as mock_close:
        await cursor_client.close()
        mock_close.assert_called_once()