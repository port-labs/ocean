from typing import Any, Literal

import pytest
from pydantic.v1 import BaseModel, Field

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.validators import (
    validate_and_get_config_schema,
)


def _resources() -> Any:
    return Field(
        default_factory=list,
        title="Resources",
        description="The list of resource configurations for the integration.",
    )


def _selector() -> Any:
    return Field(
        title="Selector",
        description="Specifies extraction flags and transformation filters reagrding the data to ingest into Port.",
    )


def test_undeclared_inherited_fields_keep_pydantic_metadata() -> None:
    class KindA(ResourceConfig):
        kind: Literal["a"] = Field(title="A", description="Kind A.")

    class Config(PortAppConfig):
        resources: list[KindA] = _resources()  # type: ignore[assignment]

    validate_and_get_config_schema(Config)
    assert KindA.__fields__["selector"].field_info.title == "Selector"
    assert KindA.__fields__["port"].field_info.title == "Port"


def test_new_selector_field_requires_title_and_description() -> None:
    class BadSelector(Selector):
        extra: str = Field(default="x", description="Missing title.")

    class BadResource(ResourceConfig):
        kind: Literal["bad"] = Field(title="Bad", description="B.")
        selector: BadSelector = _selector()

    class Config(PortAppConfig):
        resources: list[BadResource] = _resources()  # type: ignore[assignment]

    with pytest.raises(TypeError, match="must have a 'title'"):
        validate_and_get_config_schema(Config)


def test_port_app_config_root_field_requires_title() -> None:
    class KindA(ResourceConfig):
        kind: Literal["a"] = Field(title="A", description="Kind A.")

    class Config(PortAppConfig):
        extra_root: str = Field(default="x", description="Missing title.")
        resources: list[KindA] = _resources()  # type: ignore[assignment]

    with pytest.raises(
        TypeError, match="Field 'extra_root' in 'Config' must have a 'title'"
    ):
        validate_and_get_config_schema(Config)


def test_nested_model_fields_require_title_and_description() -> None:
    class Folder(BaseModel):
        path: str

    class FolderSelector(Selector):
        folders: list[Folder] = Field(title="Folders", description="Folders to export.")

    class FolderResource(ResourceConfig):
        kind: Literal["folder"] = Field(title="Folder", description="Folder kind.")
        selector: FolderSelector = _selector()

    class Config(PortAppConfig):
        resources: list[FolderResource] = _resources()  # type: ignore[assignment]

    with pytest.raises(TypeError, match="Field 'path' in 'Folder' must have a 'title'"):
        validate_and_get_config_schema(Config)


def test_redeclared_field_without_metadata_fails() -> None:
    class KindA(ResourceConfig):
        kind: Literal["a"]

    class Config(PortAppConfig):
        resources: list[KindA] = _resources()  # type: ignore[assignment]

    with pytest.raises(TypeError, match="Field 'kind' in 'KindA' must have a 'title'"):
        validate_and_get_config_schema(Config)


def test_redeclared_resources_without_metadata_fails() -> None:
    class KindA(ResourceConfig):
        kind: Literal["a"] = Field(title="A", description="Kind A.")

    class Config(PortAppConfig):
        resources: list[KindA] = Field(default_factory=list)  # type: ignore[assignment]

    with pytest.raises(
        TypeError, match="Field 'resources' in 'Config' must have a 'title'"
    ):
        validate_and_get_config_schema(Config)


def test_duplicate_literal_kinds_raise_during_schema_validation() -> None:
    class KindA(ResourceConfig):
        kind: Literal["same"] = Field(title="A", description="A.")

    class KindB(ResourceConfig):
        kind: Literal["same"] = Field(title="B", description="B.")

    class Config(PortAppConfig):
        resources: list[KindA | KindB] = _resources()  # type: ignore[assignment]

    with pytest.raises(TypeError, match="Duplicate kind"):
        validate_and_get_config_schema(Config)


def test_multi_value_kind_literal_raises_during_schema_validation() -> None:
    class Aliased(ResourceConfig):
        kind: Literal["current", "legacy"] = Field(title="Aliased", description="A.")

    class Config(PortAppConfig):
        resources: list[Aliased] = _resources()  # type: ignore[assignment]

    with pytest.raises(TypeError, match="exactly one string value"):
        validate_and_get_config_schema(Config)


def test_multiple_custom_kind_slots_raise_during_schema_validation() -> None:
    class CustomA(ResourceConfig):
        kind: str = Field(title="Custom A", description="A.")

    class CustomB(ResourceConfig):
        kind: str = Field(title="Custom B", description="B.")

    class Config(PortAppConfig):
        resources: list[CustomA | CustomB] = _resources()  # type: ignore[assignment]

    with pytest.raises(TypeError, match="Multiple custom kind"):
        validate_and_get_config_schema(Config)
