import pytest
from pydantic import ValidationError

from port_ocean.core.handlers.port_app_config.models import PortAppConfig, Selector
from port_ocean.core.handlers.port_app_config.schema_export import (
    selector_model_for_schema_export,
)
from port_ocean.core.handlers.port_app_config.validators import (
    patch_selector_definitions_for_export,
)


def test_selector_schema_export_forbids_additional_properties() -> None:
    export = selector_model_for_schema_export(Selector)
    schema = export.schema()
    assert schema.get("additionalProperties") is False


def test_base_selector_runtime_accepts_extra_keys_without_error() -> None:
    """Shared ``Selector`` ignores unknown keys; schema-only export rejects them."""
    raw = {"query": "true", "unexpected": 1}
    parsed = Selector.parse_obj(raw)
    assert parsed.query == "true"

    export = selector_model_for_schema_export(Selector)
    with pytest.raises(ValidationError):
        export.parse_obj(raw)


def test_json_schema_export_patches_selector_definitions() -> None:
    schema = PortAppConfig.schema()
    patched = patch_selector_definitions_for_export(PortAppConfig, schema)
    selector_schema = patched.get("definitions", {}).get("Selector", {})
    assert selector_schema.get("additionalProperties") is False
