from typing import Optional
from pydantic import BaseSettings
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from port_ocean.database.models.base import Base


class DatabaseSettings(BaseSettings):
    host: Optional[str] = None
    port: Optional[str] = None
    name: Optional[str] = None
    user: Optional[str] = None
    password: Optional[str] = None
    ocean_schema: Optional[str] = None

    @property
    def is_configured(self) -> bool:
        return all(
            [
                self.host,
                self.port,
                self.name,
                self.user,
                self.password,
            ]
        )

    def get_schema_name(self, integration_id: Optional[str] = None) -> str:
        if self.ocean_schema:
            return self.ocean_schema
        if not integration_id:
            raise ValueError(
                "Either ocean_schema must be set or integration_id must be provided"
            )
        return integration_id


class DatabaseManager:
    def __init__(
        self, settings: DatabaseSettings, integration_id: Optional[str] = None
    ) -> None:
        database_url = f"postgresql+psycopg://{settings.user}:{settings.password}@{settings.host}:{settings.port}/{settings.name}"
        self._engine = create_async_engine(
            database_url, echo=False, pool_pre_ping=True, pool_size=5, max_overflow=10
        )
        self._session_factory = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )
        self._schema = settings.get_schema_name(integration_id)

    async def get_session(self) -> AsyncSession:
        return self._session_factory()

    async def initialize(self) -> None:
        async with self._engine.begin() as conn:
            await conn.execute(text(f'DROP SCHEMA IF EXISTS "{self._schema}" CASCADE'))
            await conn.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{self._schema}"'))
            await conn.execute(text(f'SET search_path TO "{self._schema}"'))
            await conn.run_sync(Base.metadata.create_all)
