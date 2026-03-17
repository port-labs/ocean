from pathlib import Path
from typing import Optional

from pydantic import Field
from pydantic.env_settings import BaseSettings, EnvSettingsSource, InitSettingsSource

# Resolve .env relative to this package so it loads when run via python -m from any cwd
_HEALTH_CHECKER_DIR = Path(__file__).resolve().parent
_DEFAULT_ENV_FILE = _HEALTH_CHECKER_DIR / ".env"


class HealthCheckerSettings(BaseSettings):
    """Settings for the health checker sidecar. Loaded from env with OCEAN_HEALTH_CHECKER__ prefix."""

    url: str = Field(
        default="http://127.0.0.1:8000/isHealthy",
        description="URL of the /isHealthy endpoint to poll.",
    )
    interval_seconds: int = Field(
        default=5,
        description="Seconds between health check requests.",
        gt=0,
    )
    failure_threshold: int = Field(
        default=3,
        description="Number of consecutive failures before handling the health check as a failure.",
        gt=0,
    )
    timeout_seconds: float = Field(
        default=5.0,
        description="HTTP request timeout in seconds.",
        gt=0,
    )
    # Port API config: when set, the health checker will report resync aborted to Port on failure
    port_base_url: Optional[str] = Field(
        default=None,
        description="Port API base URL (e.g. https://api.getport.io). Required to report resync aborted to Port.",
    )
    port_client_id: Optional[str] = Field(default=None, description="Port client ID.")
    port_client_secret: Optional[str] = Field(
        default=None, description="Port client secret."
    )
    integration_identifier: Optional[str] = Field(
        default=None,
        description="Integration identifier. Required to report resync aborted to Port.",
    )
    ingest_url: Optional[str] = Field(
        default=None,
        description="Ingest service base URL (e.g. https://ingest.getport.io). Required to report resync aborted; used for syncsMetadata and abort endpoints.",
    )
    integration_type: Optional[str] = Field(
        default=None,
        description="Integration type (e.g. github, jenkins). Can be omitted if fetched from Port with integration_identifier.",
    )
    scheduled_resync_interval_minutes: Optional[int] = Field(
        default=None,
        description="Resync interval in minutes (for nextResync in state). Optional when reporting to Port.",
    )

    class Config:
        env_prefix = "OCEAN_HEALTH_CHECKER__"
        env_file = str(_DEFAULT_ENV_FILE) if _DEFAULT_ENV_FILE.exists() else None
        env_file_encoding = "utf-8"

        @classmethod
        def customise_sources(  # type: ignore
            cls,
            init_settings: InitSettingsSource,
            env_settings: EnvSettingsSource,
            *_,
            **__,
        ):
            return env_settings, init_settings
