from typing import Any, Literal

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.models import (
    CUSTOM_KIND,
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.port_app_config.validators import (
    get_port_app_config_kinds,
)


def _resources() -> Any:
    return Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the integration.",
    )


def test_get_port_app_config_kinds_returns_sorted_literal_kinds() -> None:
    class RepositoryConfig(ResourceConfig):
        kind: Literal["repository"] = Field(title="Repository", description="Repo.")

    class PullRequestConfig(ResourceConfig):
        kind: Literal["pull-request"] = Field(
            title="Pull Request",
            description="PR.",
        )

    class Config(PortAppConfig):
        resources: list[RepositoryConfig | PullRequestConfig] = _resources()  # type: ignore[assignment]

    assert get_port_app_config_kinds(Config) == ["pull-request", "repository"]


def test_get_port_app_config_kinds_skips_custom_kind_slot() -> None:
    class IncidentConfig(ResourceConfig):
        kind: Literal["incident"] = Field(title="Incident", description="Incident.")

    class CustomResourceConfig(ResourceConfig):
        kind: str = Field(title="Custom", description="Custom kind.")

    class Config(PortAppConfig):
        allow_custom_kinds = True
        resources: list[IncidentConfig | CustomResourceConfig] = _resources()  # type: ignore[assignment]

    assert get_port_app_config_kinds(Config) == ["incident"]
    assert CUSTOM_KIND not in get_port_app_config_kinds(Config)
