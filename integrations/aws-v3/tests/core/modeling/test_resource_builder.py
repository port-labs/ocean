"""Tests for ``ResourceBuilder`` output shape after the PORT-18102 optimization.

These lock in that ``build`` emits the resource ``Type`` (passed via
``with_type``) alongside the accumulated ``Properties`` as a JSON-native dict.
"""

from pydantic import BaseModel, ConfigDict

from aws.core.modeling.resource_builder import ResourceBuilder
from aws.core.modeling.resource_models import ResourceModel


class _FakeProperties(BaseModel):
    model_config = ConfigDict(extra="allow")


class _FakeResource(ResourceModel[_FakeProperties]):
    Type: str = "Test::Fake::Resource"
    Properties: _FakeProperties = _FakeProperties()


class TestResourceBuilder:
    def test_build_returns_type_and_properties(self) -> None:
        result = (
            ResourceBuilder[_FakeResource, _FakeProperties](_FakeResource)
            .with_properties({"Name": "example", "Size": 42})
            .with_type("Test::Override::Type")
            .build()
        )

        assert result == {
            "Type": "Test::Override::Type",
            "Properties": {"Name": "example", "Size": 42},
        }

    def test_repeated_with_properties_replaces(self) -> None:
        result = (
            ResourceBuilder[_FakeResource, _FakeProperties](_FakeResource)
            .with_properties({"Name": "first"})
            .with_properties({"Name": "second"})
            .with_type("Test::Fake::Resource")
            .build()
        )

        assert result["Properties"] == {"Name": "second"}
