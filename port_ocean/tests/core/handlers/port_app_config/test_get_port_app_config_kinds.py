from typing import ClassVar, Literal

from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.models import (
    CUSTOM_KIND,
    PortAppConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.port_app_config.validators import (
    get_kind_probe_permissions,
    get_port_app_config_kinds,
    validate_and_get_config_schema,
)
from port_ocean.tests.core.handlers.port_app_config.test_helpers import resources_field


def test_get_port_app_config_kinds_returns_sorted_literal_kinds() -> None:
    class RepositoryConfig(ResourceConfig):
        kind: Literal["repository"] = Field(title="Repository", description="Repo.")

    class PullRequestConfig(ResourceConfig):
        kind: Literal["pull-request"] = Field(
            title="Pull Request",
            description="PR.",
        )

    class Config(PortAppConfig):
        resources: list[RepositoryConfig | PullRequestConfig] = resources_field()  # type: ignore[assignment]

    assert get_port_app_config_kinds(Config) == ["pull-request", "repository"]


def test_get_port_app_config_kinds_skips_custom_kind_slot() -> None:
    class IncidentConfig(ResourceConfig):
        kind: Literal["incident"] = Field(title="Incident", description="Incident.")

    class CustomResourceConfig(ResourceConfig):
        kind: str = Field(title="Custom", description="Custom kind.")

    class Config(PortAppConfig):
        allow_custom_kinds: ClassVar[bool] = True
        resources: list[IncidentConfig | CustomResourceConfig] = resources_field()  # type: ignore[assignment]

    assert get_port_app_config_kinds(Config) == ["incident"]
    assert CUSTOM_KIND not in get_port_app_config_kinds(Config)


def test_get_port_app_config_kinds_includes_custom_kind_slot_with_probe_permissions() -> (
    None
):
    class IncidentConfig(ResourceConfig):
        kind: Literal["incident"] = Field(title="Incident", description="Incident.")

    class CustomResourceConfig(ResourceConfig):
        probe_permissions: ClassVar[tuple[str, ...]] = ("custom:list",)

        kind: str = Field(title="Custom", description="Custom kind.")

    class Config(PortAppConfig):
        allow_custom_kinds: ClassVar[bool] = True
        resources: list[IncidentConfig | CustomResourceConfig] = resources_field()  # type: ignore[assignment]

    assert get_port_app_config_kinds(Config) == [CUSTOM_KIND, "incident"]


def test_get_kind_probe_permissions_returns_tuple_permissions() -> None:
    class ProjectConfig(ResourceConfig):
        probe_permissions: ClassVar[tuple[str, ...]] = ("BROWSE_PROJECTS",)

        kind: Literal["project"] = Field(title="Project", description="Project.")

    class UserConfig(ResourceConfig):
        probe_permissions: ClassVar[tuple[str, ...]] = ("USER_PICKER",)

        kind: Literal["user"] = Field(title="User", description="User.")

    class Config(PortAppConfig):
        resources: list[ProjectConfig | UserConfig] = resources_field()  # type: ignore[assignment]

    assert get_kind_probe_permissions(Config) == {
        "project": ("BROWSE_PROJECTS",),
        "user": ("USER_PICKER",),
    }


def test_get_kind_probe_permissions_returns_dict_permissions_by_key() -> None:
    class RepositoryConfig(ResourceConfig):
        probe_permissions: ClassVar[dict[str, tuple[str, ...]]] = {
            "pat": ("repo",),
            "app": ("metadata",),
        }

        kind: Literal["repository"] = Field(title="Repository", description="Repo.")

    class Config(PortAppConfig):
        resources: list[RepositoryConfig] = resources_field()  # type: ignore[assignment]

    assert get_kind_probe_permissions(Config, permission_key="pat") == {
        "repository": ("repo",),
    }
    assert get_kind_probe_permissions(Config, permission_key="app") == {
        "repository": ("metadata",),
    }


def test_get_kind_probe_permissions_skips_kinds_without_metadata() -> None:
    class RepositoryConfig(ResourceConfig):
        probe_permissions: ClassVar[tuple[str, ...]] = ("repo",)

        kind: Literal["repository"] = Field(title="Repository", description="Repo.")

    class UnmappedConfig(ResourceConfig):
        kind: Literal["team"] = Field(title="Team", description="Team.")

    class Config(PortAppConfig):
        resources: list[RepositoryConfig | UnmappedConfig] = resources_field()  # type: ignore[assignment]

    assert get_kind_probe_permissions(Config) == {"repository": ("repo",)}


def test_get_kind_probe_permissions_keys_custom_kind_slot_by_custom_kind() -> None:
    class RepositoryConfig(ResourceConfig):
        probe_permissions: ClassVar[tuple[str, ...]] = ("repo",)

        kind: Literal["repository"] = Field(title="Repository", description="Repo.")

    class CustomResourceConfig(ResourceConfig):
        probe_permissions: ClassVar[tuple[str, ...]] = ("custom:list",)

        kind: str = Field(title="Custom", description="Custom kind.")

    class Config(PortAppConfig):
        allow_custom_kinds: ClassVar[bool] = True
        resources: list[RepositoryConfig | CustomResourceConfig] = resources_field()  # type: ignore[assignment]

    assert get_kind_probe_permissions(Config) == {
        "repository": ("repo",),
        CUSTOM_KIND: ("custom:list",),
    }


def test_kinds_schema_includes_probe_description() -> None:
    class IncidentConfig(ResourceConfig):
        probe_description: ClassVar[str] = "  Checks incident read access.  "

        kind: Literal["incident"] = Field(title="Incident", description="Incident.")

    class CustomResourceConfig(ResourceConfig):
        probe_description: ClassVar[str] = "Checks the custom kind API."

        kind: str = Field(title="Custom", description="Custom kind.")

    class Config(PortAppConfig):
        allow_custom_kinds: ClassVar[bool] = True
        resources: list[IncidentConfig | CustomResourceConfig] = resources_field()  # type: ignore[assignment]

    kinds = validate_and_get_config_schema(Config)["kinds"]

    assert kinds["incident"]["probeDescription"] == "Checks incident read access."
    assert kinds[CUSTOM_KIND]["probeDescription"] == "Checks the custom kind API."


def test_kinds_schema_omits_empty_probe_description() -> None:
    class RepositoryConfig(ResourceConfig):
        kind: Literal["repository"] = Field(title="Repository", description="Repo.")

    class TeamConfig(ResourceConfig):
        probe_description: ClassVar[str] = "   "

        kind: Literal["team"] = Field(title="Team", description="Team.")

    class Config(PortAppConfig):
        resources: list[RepositoryConfig | TeamConfig] = resources_field()  # type: ignore[assignment]

    kinds = validate_and_get_config_schema(Config)["kinds"]

    assert "probeDescription" not in kinds["repository"]
    assert "probeDescription" not in kinds["team"]
