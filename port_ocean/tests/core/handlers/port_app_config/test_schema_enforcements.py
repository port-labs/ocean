from typing import Literal

import pytest
from pydantic.v1 import Field

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)


def test_inherited_resources_field_keeps_parent_metadata() -> None:
    class KindA(ResourceConfig):
        kind: Literal["a"] = Field(title="A", description="Kind A.")

    class Config(PortAppConfig):
        resources: list[KindA] = Field(default_factory=list)  # type: ignore[assignment]

    resources_field = Config.__fields__["resources"]
    assert resources_field.field_info.title == "Resources"
    assert resources_field.field_info.description is not None


def test_new_selector_field_requires_title_and_description() -> None:
    with pytest.raises(TypeError, match="must have a 'title'"):

        class BadSelector(Selector):
            extra: str = Field(default="x", description="Missing title.")


def test_duplicate_literal_kinds_raise_at_class_definition() -> None:
    class KindA(ResourceConfig):
        kind: Literal["same"] = Field(title="A", description="A.")

    class KindB(ResourceConfig):
        kind: Literal["same"] = Field(title="B", description="B.")

    with pytest.raises(TypeError, match="Duplicate kind"):

        class Config(PortAppConfig):
            resources: list[KindA | KindB] = Field(default_factory=list)  # type: ignore[assignment]


def test_literal_kind_aliases_are_allowed_on_one_model() -> None:
    class Aliased(ResourceConfig):
        kind: Literal["current", "legacy"] = Field(title="Aliased", description="A.")

    class Config(PortAppConfig):
        resources: list[Aliased] = Field(default_factory=list)  # type: ignore[assignment]

    from port_ocean.core.handlers.port_app_config.validators import (
        validate_and_get_config_schema,
    )

    kinds = validate_and_get_config_schema(Config)["kinds"]
    assert "current" in kinds
    assert "legacy" in kinds


def test_multiple_custom_kind_slots_raise_at_class_definition() -> None:
    class CustomA(ResourceConfig):
        kind: str = Field(title="Custom A", description="A.")

    class CustomB(ResourceConfig):
        kind: str = Field(title="Custom B", description="B.")

    with pytest.raises(TypeError, match="Multiple custom kind"):

        class Config(PortAppConfig):
            resources: list[CustomA | CustomB] = Field(default_factory=list)  # type: ignore[assignment]
