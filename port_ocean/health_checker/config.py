from pydantic import Field
from pydantic.env_settings import BaseSettings, EnvSettingsSource, InitSettingsSource


class HealthCheckerSettings(BaseSettings):
    """Settings for the health checker sidecar. Loaded from env with OCEAN_HEALTH_CHECKER__ prefix."""

    url: str = Field(
        default="http://127.0.0.1:8000/isHealthy",
        description="URL of the /isHealthy endpoint to poll.",
    )
    interval_seconds: int = Field(
        default=10,
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

    class Config:
        env_prefix = "OCEAN_HEALTH_CHECKER__"
        env_file = ".env"
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
