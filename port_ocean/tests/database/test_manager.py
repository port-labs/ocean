from typing import AsyncGenerator
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.ext.asyncio import AsyncSession, AsyncEngine

from port_ocean.database.manager import DatabaseManager, DatabaseSettings


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
def custom_schema_settings() -> DatabaseSettings:
    return DatabaseSettings(
        host="localhost",
        port="5432",
        name="test_db",
        user="test_user",
        password="test_password",
        ocean_schema="custom_schema",
    )


@pytest.fixture
def mock_engine() -> AsyncMock:
    engine = AsyncMock(spec=AsyncEngine)
    return engine


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock(spec=AsyncSession)
    return session


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    session_factory = MagicMock()
    session_factory.return_value = mock_session
    return session_factory


@pytest.fixture
async def db_manager(
    db_settings: DatabaseSettings,
    mock_engine: AsyncMock,
    mock_session_factory: MagicMock,
) -> AsyncGenerator[DatabaseManager, None]:
    with (
        patch(
            "port_ocean.database.manager.create_async_engine",
            return_value=mock_engine,
        ),
        patch(
            "port_ocean.database.manager.async_sessionmaker",
            return_value=mock_session_factory,
        ),
    ):
        manager = DatabaseManager(db_settings, integration_id="test_integration")
        yield manager


@pytest.fixture
async def custom_schema_manager(
    custom_schema_settings: DatabaseSettings,
    mock_engine: AsyncMock,
    mock_session_factory: MagicMock,
) -> AsyncGenerator[DatabaseManager, None]:
    with (
        patch(
            "port_ocean.database.manager.create_async_engine",
            return_value=mock_engine,
        ),
        patch(
            "port_ocean.database.manager.async_sessionmaker",
            return_value=mock_session_factory,
        ),
    ):
        manager = DatabaseManager(custom_schema_settings)
        yield manager


@pytest.mark.asyncio
async def test_database_manager_initialization(
    db_manager: DatabaseManager, mock_engine: AsyncMock, mock_session_factory: MagicMock
) -> None:
    """Test that the database manager initializes correctly with integration_id."""
    assert db_manager._schema == "test_integration"
    assert db_manager._engine == mock_engine
    assert db_manager._session_factory == mock_session_factory


@pytest.mark.asyncio
async def test_custom_schema_initialization(
    custom_schema_manager: DatabaseManager,
    mock_engine: AsyncMock,
    mock_session_factory: MagicMock,
) -> None:
    """Test that the database manager initializes correctly with custom schema."""
    assert custom_schema_manager._schema == "custom_schema"
    assert custom_schema_manager._engine == mock_engine
    assert custom_schema_manager._session_factory == mock_session_factory


@pytest.mark.asyncio
async def test_get_session(
    db_manager: DatabaseManager, mock_session: AsyncMock
) -> None:
    """Test that get_session returns a valid session."""
    session = await db_manager.get_session()
    assert session == mock_session


@pytest.mark.asyncio
async def test_get_schema_name_validation() -> None:
    """Test that get_schema_name validates inputs correctly."""
    settings = DatabaseSettings(
        host="localhost",
        port="5432",
        name="test_db",
        user="test_user",
        password="test_password",
        ocean_schema="custom_schema",
    )

    # Test with custom schema
    assert settings.get_schema_name() == "custom_schema"

    # Test with integration_id
    settings.ocean_schema = None
    assert settings.get_schema_name("test_integration") == "test_integration"

    # Test with neither
    with pytest.raises(ValueError):
        settings.get_schema_name()
