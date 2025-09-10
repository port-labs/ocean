import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.context.ocean import ocean


@pytest.fixture(autouse=True)
def mock_ocean_context():
    """Mock Ocean context for testing."""
    with patch("port_ocean.context.ocean.ocean") as mock_ocean:
        mock_ocean.integration_config = {
            "api_key": "test-api-key",
            "team_id": "test-team-id"
        }
        yield mock_ocean


@pytest.fixture
def mock_cursor_client():
    """Mock CursorClient for testing."""
    client = AsyncMock()
    client.api_key = "test-api-key"
    client.team_id = "test-team-id"
    client.get_team_info = AsyncMock()
    client.get_team_members = AsyncMock()
    client.get_daily_usage_data = AsyncMock()
    client.get_ai_commit_metrics = AsyncMock()
    client.get_ai_code_changes = AsyncMock()
    client.get_filtered_usage_events = AsyncMock()
    client.get_user_daily_usage = AsyncMock()
    client.close = AsyncMock()
    return client


@pytest.fixture
def sample_team_data():
    """Sample team data for testing."""
    return {
        "id": "test-team-id",
        "name": "Test Team",
        "description": "A test team for development",
        "member_count": 5,
        "plan_type": "pro",
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T12:00:00Z"
    }


@pytest.fixture
def sample_user_data():
    """Sample user data for testing."""
    return [
        {
            "id": "user1",
            "email": "user1@example.com",
            "name": "User One",
            "role": "admin",
            "status": "active",
            "joined_at": "2024-01-01T00:00:00Z",
            "last_active_at": "2024-01-15T10:00:00Z",
            "team_id": "test-team-id"
        },
        {
            "id": "user2", 
            "email": "user2@example.com",
            "name": "User Two",
            "role": "member",
            "status": "active",
            "joined_at": "2024-01-02T00:00:00Z",
            "last_active_at": "2024-01-15T09:30:00Z",
            "team_id": "test-team-id"
        }
    ]


@pytest.fixture
def sample_daily_usage_data():
    """Sample daily usage data for testing."""
    return [
        {
            "date": "2024-01-15",
            "total_active_time_minutes": 240,
            "ai_interactions": 50,
            "lines_generated": 1200,
            "suggestions_accepted": 40,
            "suggestions_rejected": 10,
            "files_modified": 15,
            "user_email": "user1@example.com",
            "team_id": "test-team-id"
        },
        {
            "date": "2024-01-14",
            "total_active_time_minutes": 180,
            "ai_interactions": 35,
            "lines_generated": 800,
            "suggestions_accepted": 30,
            "suggestions_rejected": 5,
            "files_modified": 12,
            "user_email": "user1@example.com",
            "team_id": "test-team-id"
        }
    ]


@pytest.fixture
def sample_ai_commit_data():
    """Sample AI commit data for testing."""
    return [
        {
            "commit_hash": "abc123def456",
            "repository": "test-repo",
            "author_name": "User One",
            "author_email": "user1@example.com", 
            "message": "Add new feature with AI assistance",
            "timestamp": "2024-01-15T14:30:00Z",
            "ai_assistance_level": "high",
            "ai_generated_percentage": 75,
            "lines_added": 150,
            "lines_removed": 20,
            "files_changed": 3,
            "branch": "feature/new-functionality",
            "team_id": "test-team-id"
        }
    ]


@pytest.fixture
def sample_usage_events_data():
    """Sample usage events data for testing."""
    return [
        {
            "event_id": "event123",
            "timestamp": "2024-01-15T10:00:00Z",
            "user_email": "user1@example.com",
            "event_type": "ai_interaction",
            "duration_seconds": 120,
            "metadata": {"prompt_type": "code_completion"},
            "session_id": "session123",
            "file_name": "main.py",
            "language": "python",
            "team_id": "test-team-id"
        },
        {
            "event_id": "event124",
            "timestamp": "2024-01-15T10:05:00Z",
            "user_email": "user1@example.com",
            "event_type": "suggestion_accepted",
            "duration_seconds": 5,
            "metadata": {"suggestion_type": "function"},
            "session_id": "session123",
            "file_name": "main.py", 
            "language": "python",
            "team_id": "test-team-id"
        }
    ]