"""Tests for ``ResourceBuilder`` misuse handling and ``Type`` resolution.

These lock in two behaviours the builder must preserve after the
PORT-18102 optimization:

* builder misuse raises a dedicated ``ResourceBuilderError`` (not a bare
  ``ValueError``) so callers can catch it precisely;
* the built dict always carries ``Type`` - either the value passed via
  ``with_type`` or the model's own default - and fails explicitly when
  neither is available.
"""

import pytest
from pydantic.v1 import BaseModel

from aws.core.modeling.resource_builder import (
    ResourceBuilder,
    ResourceBuilderError,
)
from aws.core.modeling.resource_models import ResourceModel


class _FakeProperties(BaseModel):
    class Config:
        extra = "allow"


class _FakeResource(ResourceModel[_FakeProperties]):
    Type: str = "Test::Fake::Resource"
    Properties: _FakeProperties = _FakeProperties()


class _NoDefaultTypeResource(ResourceModel[_FakeProperties]):
    """Mirrors the abstract base: ``Type`` is required with no default."""

    Properties: _FakeProperties = _FakeProperties()


class TestResourceBuilderMisuse:
    def test_build_without_properties_raises_resource_builder_error(self) -> None:
        builder = ResourceBuilder[_FakeResource, _FakeProperties](_FakeResource)

        with pytest.raises(ResourceBuilderError):
            builder.build()

    def test_build_without_type_and_no_default_raises_resource_builder_error(
        self,
    ) -> None:
        builder = ResourceBuilder[_NoDefaultTypeResource, _FakeProperties](
            _NoDefaultTypeResource
        )
        builder.with_properties({"Name": "example"})

        with pytest.raises(ResourceBuilderError):
            builder.build()


class TestResourceBuilderTypeResolution:
    def test_explicit_type_is_used(self) -> None:
        builder = ResourceBuilder[_FakeResource, _FakeProperties](_FakeResource)
        result = (
            builder.with_properties({"Name": "example"})
            .with_type("Test::Override::Type")
            .build()
        )

        assert result["Type"] == "Test::Override::Type"
        assert result["Properties"] == {"Name": "example"}

    def test_falls_back_to_model_default_type(self) -> None:
        builder = ResourceBuilder[_FakeResource, _FakeProperties](_FakeResource)
        result = builder.with_properties({"Name": "example"}).build()

        assert result["Type"] == "Test::Fake::Resource"
        assert result["Properties"] == {"Name": "example"}
