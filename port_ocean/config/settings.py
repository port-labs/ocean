from typing import Any, Literal, Optional, Self, Type
from urllib.parse import urlparse

import os

from loguru import logger
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    TypeAdapter,
    field_validator,
    model_validator,
)
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)

from port_ocean.config.base import BaseOceanModel, BaseOceanSettings, sensitive_field
from port_ocean.config.dynamic import NoTrailingSlashUrl
from port_ocean.core.event_listener import (
    EventListenerSettingsType,
    PollingEventListenerSettings,
)
from port_ocean.core.models import (
    CachingStorageMode,
    CreatePortResourcesOrigin,
    EventListenerType,
    LiveEventsConsumerType,
    ProcessingMode,
    Runtime,
)
from port_ocean.utils.misc import (
    get_cgroup_cpu_limit,
    get_integration_name,
    get_spec_file,
)
from port_ocean.utils.time import parse_interval_to_minutes

LogLevelType = Literal["ERROR", "WARNING", "INFO", "DEBUG", "CRITICAL"]
ALLOWED_INCREMENTAL_SYNC_INTERVALS = (15, 30, 60)


class SslX509Settings(BaseOceanModel):
    """X.509 verification profile applied when ``verify`` is true."""

    strict: bool = True


class SslClientSettings(BaseOceanModel):
    verify: bool = True
    x509: SslX509Settings = Field(default_factory=SslX509Settings)


class SslSettings(BaseOceanModel):
    port: SslClientSettings = Field(default_factory=SslClientSettings)
    third_party: SslClientSettings = Field(default_factory=SslClientSettings)


class ApplicationSettings(BaseSettings):
    log_level: LogLevelType = "INFO"
    enable_http_logging: bool = True
    port: int = 8000

    model_config = SettingsConfigDict(
        env_prefix="APPLICATION__",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        *_: Any,
        **__: Any,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return env_settings, dotenv_settings, init_settings


class PortSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    client_id: str = sensitive_field()
    client_secret: str = sensitive_field()
    base_url: NoTrailingSlashUrl = "https://api.getport.io"
    port_app_config_cache_ttl: int = 60
    feature_flags_cache_ttl_seconds: float = 300.0  # 5 minutes
    blueprint_cache_ttl_seconds: float = 120.0


class IntegrationSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    identifier: str
    type: str
    config: Any = Field(default_factory=dict)
    incremental_sync_enabled: bool = False
    incremental_sync_interval: int = (
        15  # minutes; env may be "15m", "1h", or bare minutes
    )

    @field_validator("incremental_sync_interval", mode="before")
    @classmethod
    def parse_incremental_sync_interval(cls, value: Any) -> int:
        if value is None:
            return 15
        minutes = parse_interval_to_minutes(value)
        if minutes not in ALLOWED_INCREMENTAL_SYNC_INTERVALS:
            raise ValueError(
                f"incremental_sync_interval must be one of "
                f"{ALLOWED_INCREMENTAL_SYNC_INTERVALS}, got {minutes}"
            )
        return minutes

    @model_validator(mode="before")
    @classmethod
    def root_validator(cls, values: dict[str, Any]) -> dict[str, Any]:
        integ_type = values.get("type")

        if not integ_type:
            integ_type = get_integration_name()

        values["type"] = integ_type.lower() if integ_type else None
        if not values.get("identifier"):
            values["identifier"] = f"my-{integ_type}-integration".lower()

        return values


class MetricsSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=False)
    webhook_url: str | None = Field(default=None)


class StreamingSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=False)
    max_buffer_size_mb: int = Field(default=1024 * 1024 * 20)  # 20 mb
    chunk_size: int = Field(default=1024 * 64)  # 64 kb
    location: str = Field(default="/tmp/ocean/streaming")


class ActionsProcessorSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    enabled: bool = Field(default=False)
    runs_buffer_high_watermark: int = Field(
        default=300,
        ge=1,
        le=1_000,
        description=(
            "Max total runs queued across all actions before throttling "
            "claim-pending polls. Aligned with Port's claim-pending limit."
        ),
    )
    visibility_timeout_ms: int = Field(
        default=60_000,
        ge=1,
        le=600_000,
        description=(
            "How long a claimed run stays invisible to other consumers before "
            "becoming reclaimable (milliseconds)."
        ),
    )
    poll_check_interval_seconds: int = Field(
        default=10,
        ge=1,
        description="Seconds between claim-pending polling attempts.",
    )
    workers_count: int = Field(
        default=3,
        ge=1,
        description=(
            "Number of concurrent worker tasks processing claimed runs. "
            "Tune based on the CPU and memory allocated to the pod."
        ),
    )
    max_runs_buffer_util_pct_per_action: int | None = Field(
        default=30,
        ge=1,
        le=100,
        description=(
            "Max runs-buffer utilization percentage per action. When queued runs "
            "for an action identifier reach this % of runs_buffer_high_watermark, "
            "exclude it from claim-pending."
        ),
    )


class LiveEventsRedisSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    url: str = Field(default="redis://localhost:6379")
    username: str | None = None
    password: str | None = sensitive_field(default=None)
    enable_tls: bool = False
    ca: str | None = Field(
        default=None,
        description="Base64-encoded PEM CA certificate bundle for TLS verification.",
    )
    cert: str | None = Field(
        default=None,
        description="Base64-encoded PEM client certificate for mutual TLS.",
    )
    private_key: str | None = sensitive_field(
        default=None,
        description="Base64-encoded PEM private key for mutual TLS.",
    )
    block_ms: int = Field(default=1000, ge=1)
    read_count: int = Field(
        default=10,
        ge=1,
        description="Maximum number of stream entries to return per XREADGROUP call.",
    )
    stream_ttl_seconds: int | None = Field(
        default=2_592_000,  # 30 days
        ge=1,
        description=(
            "TTL in seconds for the Redis stream. Set when the consumer creates "
            "the stream via MKSTREAM. Set to null to disable stream expiry."
        ),
    )
    # Redis stream maintenance worker settings
    stream_maintenance_worker_enabled: bool = Field(
        default=True,
        description=(
            "When true, starts a background worker that reclaims stuck PEL "
            "entries, re-enqueues them for reprocessing, and removes idle "
            "consumers from the group."
        ),
    )
    pel_stuck_timeout_seconds: int = Field(
        default=600,
        ge=1,
        description=(
            "Seconds a PEL entry must be idle before the maintenance worker "
            "reclaims it."
        ),
    )
    pel_max_requeue_count: int = Field(
        default=3,
        ge=1,
        description="Maximum number of times a message is requeued before being discarded.",
    )
    stream_maintenance_scan_interval_seconds: float = Field(
        default=30.0,
        gt=0,
        description=(
            "Seconds between successive maintenance worker scans of the "
            "consumer group."
        ),
    )
    pel_xautoclaim_count: int = Field(
        default=100,
        ge=1,
        description="Maximum number of PEL entries to claim per XAUTOCLAIM call.",
    )
    stream_maintenance_error_backoff_seconds: float = Field(
        default=5.0,
        gt=0,
        description=(
            "Seconds to wait before retrying the stream maintenance worker loop "
            "after an unexpected error."
        ),
    )
    stream_maintenance_consumer_cleanup_enabled: bool = Field(
        default=True,
        description=(
            "When true, the stream maintenance worker periodically removes idle "
            "consumers from the group that have no pending messages."
        ),
    )
    stream_maintenance_consumer_cleanup_idle_seconds: int = Field(
        default=86_400,  # 24 hours
        ge=1,
        description=(
            "Seconds a consumer must be idle before the maintenance worker "
            "removes it from the consumer group."
        ),
    )
    connection_error_backoff_seconds: float = Field(
        default=5.0,
        gt=0,
        description=(
            "Seconds to wait before retrying the Redis stream read loop "
            "after a connection error."
        ),
    )
    connection_startup_max_retries: int = Field(
        default=5,
        ge=0,
        description=(
            "Maximum number of connection retries when establishing the "
            "initial Redis client at startup."
        ),
    )
    connection_startup_initial_backoff_seconds: float = Field(
        default=1.0,
        gt=0,
        description=(
            "Initial delay in seconds before the first Redis startup "
            "connection retry."
        ),
    )
    connection_startup_exponential_base: float = Field(
        default=2.0,
        gt=0,
        description=(
            "Exponential base used to calculate Redis startup connection "
            "retry delays."
        ),
    )

    @property
    def stuck_timeout_ms(self) -> int:
        return self.pel_stuck_timeout_seconds * 1000

    @property
    def consumer_cleanup_idle_ms(self) -> int:
        return self.stream_maintenance_consumer_cleanup_idle_seconds * 1000

    @model_validator(mode="after")
    def validate_tls_settings(self) -> Self:
        scheme = urlparse(self.url).scheme.lower()
        uses_tls_scheme = scheme == "rediss"

        if self.enable_tls and not uses_tls_scheme:
            raise ValueError(
                "enable_tls is True but the Redis URL does not use the rediss:// "
                "scheme. Use a rediss:// URL or set enable_tls to False."
            )
        if not self.enable_tls and uses_tls_scheme:
            raise ValueError(
                "The Redis URL uses rediss:// but enable_tls is False. "
                "Set enable_tls to True or use a redis:// URL."
            )

        has_cert = bool(self.cert)
        has_private_key = bool(self.private_key)
        if has_cert != has_private_key:
            raise ValueError(
                "Redis mutual TLS requires both cert and private_key to be set."
            )

        return self


class LiveEventsSettings(BaseOceanModel):
    model_config = ConfigDict(extra="allow")

    type: LiveEventsConsumerType = LiveEventsConsumerType.REDIS
    is_redis_stream_consumer_enabled: bool = False


class RedisLiveEventsSettings(LiveEventsSettings):
    type: Literal[LiveEventsConsumerType.REDIS] = LiveEventsConsumerType.REDIS
    redis: LiveEventsRedisSettings = Field(default_factory=LiveEventsRedisSettings)


LiveEventsSettingsType = RedisLiveEventsSettings


class IntegrationConfiguration(BaseOceanSettings):
    model_config = SettingsConfigDict(extra="allow")

    integration_config_model: Type[BaseModel] | None = Field(default=None, exclude=True)

    allow_environment_variables_jq_access: bool = True
    initialize_port_resources: bool = True
    scheduled_resync_interval: int | None = None
    status_heartbeat_interval_seconds: int = Field(
        default=10,  # Interval in seconds for sending metrics heartbeat (liveness).
        gt=0,
    )
    client_timeout: int = 60
    create_port_resources_origin: CreatePortResourcesOrigin | None = None
    send_raw_data_examples: bool = True
    oauth_access_token_file_path: str | None = None
    base_url: str | None = None
    path_prefix: str | None = None
    port: PortSettings
    event_listener: EventListenerSettingsType = Field(
        default_factory=lambda: PollingEventListenerSettings(
            type=EventListenerType.POLLING
        )
    )
    event_workers_count: int = 1
    events_debug_logging: bool = False
    # If an identifier or type is not provided, it will be generated based on the integration name
    integration: IntegrationSettings = Field(
        default_factory=lambda: IntegrationSettings(type="", identifier="")
    )
    runtime: Runtime = Runtime.OnPrem
    resources_path: str = Field(default=".port/resources")
    metrics: MetricsSettings = Field(
        default_factory=lambda: MetricsSettings(enabled=False, webhook_url=None)
    )
    max_event_processing_seconds: float = 90.0
    max_wait_seconds_before_shutdown: float = 5.0
    caching_storage_mode: Optional[CachingStorageMode] = Field(
        default=CachingStorageMode.disk
    )

    upsert_entities_batch_max_length: int = 20
    upsert_entities_batch_max_size_in_bytes: int = 1024 * 1024
    lakehouse_enabled: bool = True
    disable_ip_outbound_blocker: bool | None = None
    lakehouse_buffer_interval_seconds: float = 10.0
    lakehouse_buffer_max_count: int = 50
    processing_mode: ProcessingMode = ProcessingMode.dsp
    yield_items_to_parse_batch_size: int = 200
    process_in_queue_timeout: int = 120
    process_in_queue_max_workers: int = Field(
        default_factory=lambda: get_cgroup_cpu_limit()
    )
    delete_entities_max_batch_size: int = 1000
    streaming: StreamingSettings = Field(default_factory=StreamingSettings)
    actions_processor: ActionsProcessorSettings = Field(
        default_factory=ActionsProcessorSettings
    )
    live_events: LiveEventsSettingsType = Field(default_factory=RedisLiveEventsSettings)
    ssl: SslSettings = Field(default_factory=SslSettings)

    @model_validator(mode="before")
    @classmethod
    def warn_removed_process_execution_mode_env(cls, values: Any) -> Any:
        process_execution_mode = os.environ.get("OCEAN__PROCESS_EXECUTION_MODE")
        if process_execution_mode:
            logger.warning(
                "OCEAN__PROCESS_EXECUTION_MODE is no longer supported and will be ignored. "
                "Ocean always runs in single_process mode.",
                process_execution_mode=process_execution_mode,
            )
        return values

    @field_validator("metrics", mode="before")
    @classmethod
    def validate_metrics(cls, v: Any) -> MetricsSettings | dict[str, Any] | None:
        if v is None:
            return MetricsSettings(enabled=False, webhook_url=None)
        if isinstance(v, dict):
            return v
        if isinstance(v, MetricsSettings):
            return v
        # Try to convert to dict for other types
        try:
            return dict(v)
        except (TypeError, ValueError):
            return MetricsSettings(enabled=False, webhook_url=None)

    @model_validator(mode="after")
    def set_disable_ip_outbound_blocker_default(self) -> Self:
        if self.disable_ip_outbound_blocker is None:
            self.disable_ip_outbound_blocker = not self.runtime.is_saas_runtime
        return self

    @model_validator(mode="after")
    def validate_integration_config(self) -> Self:
        if not (config_model := self.integration_config_model):
            return self

        # Using the integration dynamic config model to parse the config
        def parse_config(model: Type[BaseModel], config: Any) -> BaseModel:
            # In some cases, the config is parsed as a string so we need to handle it
            # Example: when the config is loaded from the environment variables and there is an object inside the config
            if isinstance(config, str):
                return TypeAdapter(model).validate_json(config)
            else:
                return TypeAdapter(model).validate_python(config)

        self.integration.config = parse_config(config_model, self.integration.config)
        return self

    @field_validator("runtime")
    @classmethod
    def validate_runtime(cls, runtime: Runtime) -> Runtime:
        if runtime.is_saas_runtime:
            spec = get_spec_file()
            if spec is None:
                raise ValueError(
                    "Could not determine whether it's safe to run "
                    "the integration due to not found spec.json or spec.yaml."
                )

            saas_config = spec.get("saas")
            if saas_config and not saas_config["enabled"]:
                raise ValueError("This integration can't be ran as Saas")

        return runtime

    @field_validator("actions_processor")
    @classmethod
    def validate_actions_processor(
        cls, actions_processor: ActionsProcessorSettings
    ) -> ActionsProcessorSettings:
        if not actions_processor.enabled:
            return actions_processor

        spec = get_spec_file()
        if not (spec and spec.get("actionsProcessingEnabled", False)):
            raise ValueError(
                "Serving as an actions processor is not currently supported for this integration."
            )

        return actions_processor
