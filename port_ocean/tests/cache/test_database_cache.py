import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from port_ocean.cache.database import DatabaseCacheProvider
from port_ocean.database.manager import DatabaseManager, DatabaseSettings
from port_ocean.database.models.cache import CacheEntry


@pytest.fixture
def db_settings() -> DatabaseSettings:
    return DatabaseSettings(
        host="localhost",
        port="5432",
        name="test_db",
        user="test_user",
        password="test_password",
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    # Set up the session's execute method to return a mock result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute.return_value = mock_result
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    session_factory = MagicMock()
    session_factory.return_value = mock_session
    return session_factory


@pytest.fixture
def mock_db_manager(
    db_settings: DatabaseSettings, mock_session_factory: MagicMock
) -> DatabaseManager:
    manager = DatabaseManager(db_settings, integration_id="test_integration")
    manager._session_factory = mock_session_factory
    return manager


@pytest.fixture
def database_cache(mock_db_manager: DatabaseManager) -> DatabaseCacheProvider:
    return DatabaseCacheProvider(mock_db_manager)


@pytest.mark.asyncio
async def test_database_cache_set_get_single_value(
    database_cache: DatabaseCacheProvider,
    mock_session: AsyncMock,
    mock_db_manager: DatabaseManager,
) -> None:
    """Test setting and getting a single value from database cache."""
    test_key = "test_key"
    test_value = {"data": "test_value"}

    # Mock the session execute and scalars
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        CacheEntry(
            cache_key=test_key,
            result=test_value,
            created_at=datetime.now(timezone.utc),
        )
    ]
    mock_session.execute.return_value = mock_result

    # Set up the session as an async context manager
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    # Mock get_session to return our mock session
    with patch.object(mock_db_manager, "get_session", return_value=mock_session):
        # Test set
        await database_cache.set(test_key, test_value)
        assert mock_session.add.call_count == 1
        mock_session.commit.assert_called_once()

        # Test get
        result = await database_cache.get(test_key)
        assert result == test_value


@pytest.mark.asyncio
async def test_database_cache_set_get_list_value(
    database_cache: DatabaseCacheProvider,
    mock_session: AsyncMock,
    mock_db_manager: DatabaseManager,
) -> None:
    """Test setting and getting a list of values from database cache."""
    test_key = "test_key"
    test_values = [{"data": "value1"}, {"data": "value2"}]

    # Mock the session execute and scalars
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [
        CacheEntry(
            cache_key=test_key,
            result=value,
            created_at=datetime.now(timezone.utc),
        )
        for value in test_values
    ]
    mock_session.execute.return_value = mock_result

    # Set up the session as an async context manager
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    # Mock get_session to return our mock session
    with patch.object(mock_db_manager, "get_session", return_value=mock_session):
        # Test set
        await database_cache.set(test_key, test_values)
        assert mock_session.add.call_count == len(test_values)
        mock_session.commit.assert_called_once()

        # Test get
        result = await database_cache.get(test_key)
        assert result == test_values


@pytest.mark.asyncio
async def test_database_cache_get_nonexistent(
    database_cache: DatabaseCacheProvider,
    mock_session: AsyncMock,
    mock_db_manager: DatabaseManager,
) -> None:
    """Test getting a nonexistent value from database cache."""
    test_key = "nonexistent_key"

    # Mock the session execute and scalars to return empty list
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute.return_value = mock_result

    # Set up the session as an async context manager
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    # Mock get_session to return our mock session
    with patch.object(mock_db_manager, "get_session", return_value=mock_session):
        result = await database_cache.get(test_key)
        assert result is None


@pytest.mark.asyncio
async def test_database_cache_clear(
    database_cache: DatabaseCacheProvider,
    mock_session: AsyncMock,
    mock_db_manager: DatabaseManager,
) -> None:
    """Test clearing all values from database cache."""
    # Mock the session execute
    mock_result = MagicMock()
    mock_session.execute.return_value = mock_result

    # Set up the session as an async context manager
    mock_session.__aenter__.return_value = mock_session
    mock_session.__aexit__.return_value = None

    # Mock get_session to return our mock session
    with patch.object(mock_db_manager, "get_session", return_value=mock_session):
        await database_cache.clear()
        mock_session.execute.assert_called_once()
        mock_session.commit.assert_called_once()
