"""Harbor integration entry point and runtime configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal, Optional

from pydantic.v1 import BaseModel, Field, validator

from port_ocean.context.ocean import ocean
from port_ocean.core.handlers.port_app_config.api import APIPortAppConfig
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.integrations.base import BaseIntegration

from integrations.harbor.client import HarborClient
from integrations.harbor.webhooks import HarborWebhookProcessor


def _split_csv(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.split(",") if item.strip()]
    if isinstance(value, (list, tuple)):
        return [str(item).strip() for item in value if str(item).strip()]
    return []


class HarborIntegrationSettings(BaseModel):
    base_url: str = Field(alias="baseUrl")
    auth_mode: Literal["robot_token", "basic", "oidc"] = Field(
        default="robot_token", alias="authMode"
    )
    robot_account: Optional[str] = Field(default=None, alias="robotAccount")
    robot_token: Optional[str] = Field(default=None, alias="robotToken")
    username: Optional[str] = None
    password: Optional[str] = None
    oidc_access_token: Optional[str] = Field(default=None, alias="oidcAccessToken")
    timeout: Optional[float] = None
    webhook_secret: Optional[str] = Field(default=None, alias="webhookSecret")

    projects: list[str] = Field(default_factory=list, alias="projects")
    project_visibility_filter: list[str] = Field(
        default_factory=list, alias="projectVisibilityFilter"
    )
    project_name_prefix: Optional[str] = Field(default=None, alias="projectNamePrefix")

    repository_project_filter: list[str] = Field(
        default_factory=list, alias="repositoryProjectFilter"
    )
    repository_name_prefix: Optional[str] = Field(
        default=None, alias="repositoryNamePrefix"
    )
    repository_name_contains: Optional[str] = Field(
        default=None, alias="repositoryNameContains"
    )

    artifact_tag_filter: list[str] = Field(
        default_factory=list, alias="artifactTagFilter"
    )
    artifact_digest_filter: list[str] = Field(
        default_factory=list, alias="artifactDigestFilter"
    )
    artifact_label_filter: list[str] = Field(
        default_factory=list, alias="artifactLabelFilter"
    )
    artifact_media_type_filter: list[str] = Field(
        default_factory=list, alias="artifactMediaTypeFilter"
    )
    artifact_created_since: Optional[str] = Field(
        default=None, alias="artifactCreatedSince"
    )
    artifact_vuln_severity_at_least: Optional[str] = Field(
        default=None, alias="artifactVulnSeverityAtLeast"
    )
    max_concurrency: int = Field(default=5, alias="maxConcurrentRequests")
    max_retries: int = Field(default=5, alias="maxRetries")
    retry_jitter_seconds: float = Field(default=0.5, alias="retryJitterSeconds")
    log_level: Optional[str] = Field(default=None, alias="logLevel")
    port_org_id: Optional[str] = Field(default=None, alias="portOrgId")

    class Config:
        allow_population_by_field_name = True

    @validator(
        "projects",
        "project_visibility_filter",
        "repository_project_filter",
        "artifact_tag_filter",
        "artifact_digest_filter",
        "artifact_label_filter",
        "artifact_media_type_filter",
        pre=True,
    )
    def _split_list(cls, value: Any) -> list[str]:  # noqa: N805
        return _split_csv(value)

    @validator("auth_mode", pre=True)
    def _normalise_auth_mode(cls, value: Any) -> str:  # noqa: N805
        if isinstance(value, str):
            lower = value.lower().strip()
            if lower in {"robot_token", "basic", "oidc"}:
                return lower
        return "robot_token"

    @validator("base_url", pre=True)
    def _coerce_base_url(cls, value: Any) -> str:  # noqa: N805
        if isinstance(value, str):
            return value.strip()
        return str(value)

    @validator("max_concurrency", "max_retries", pre=True)
    def _non_negative_int(cls, value: Any) -> int:  # noqa: N805
        try:
            parsed = int(value)
        except (TypeError, ValueError):
            return 5
        return max(parsed, 1)


@dataclass
class HarborIntegrationRuntime:
    settings: HarborIntegrationSettings

    def create_client(self) -> HarborClient:
        return HarborClient(
            base_url=self.settings.base_url,
            auth_mode=self.settings.auth_mode,
            robot_account=self.settings.robot_account,
            robot_token=self.settings.robot_token,
            username=self.settings.username,
            password=self.settings.password,
            oidc_access_token=self.settings.oidc_access_token,
            default_timeout=self.settings.timeout,
            max_retries=self.settings.max_retries,
            max_concurrency=self.settings.max_concurrency,
            jitter_seconds=self.settings.retry_jitter_seconds,
        )

    def resolve_port_org_id(self) -> str | None:
        explicit = self.settings.port_org_id
        if isinstance(explicit, str) and (stripped := explicit.strip()):
            return stripped

        config_value = ocean.integration_config.get("portOrgId")
        if isinstance(config_value, str) and (stripped := config_value.strip()):
            return stripped

        return None


class HarborPortAppConfig(PortAppConfig):
    """Harbor port app configuration placeholder."""


_runtime: HarborIntegrationRuntime | None = None
_webhook_registered: bool = False


class HarborIntegration(BaseIntegration):
    """Harbor integration entry point."""

    runtime: HarborIntegrationRuntime

    class AppConfigHandlerClass(APIPortAppConfig):
        CONFIG_CLASS = HarborPortAppConfig

    def __init__(self, context):  # type: ignore[override]
        super().__init__(context)

        settings = HarborIntegrationSettings.parse_obj(context.integration_config)
        self.runtime = HarborIntegrationRuntime(settings)

        global _runtime  # noqa: PLW0603
        _runtime = self.runtime

        global _webhook_registered  # noqa: PLW0603
        if not _webhook_registered:
            ocean.add_webhook_processor("/webhook", HarborWebhookProcessor)
            _webhook_registered = True


def get_runtime() -> HarborIntegrationRuntime:
    """Return the cached integration runtime, creating it if necessary."""

    global _runtime  # noqa: PLW0603
    if _runtime is None:
        settings = HarborIntegrationSettings.parse_obj(ocean.integration_config)
        _runtime = HarborIntegrationRuntime(settings)
    return _runtime
