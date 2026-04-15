from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    ResourceConfig,
    Selector,
)
from port_ocean.core.handlers.port_app_config.validators import (
    _get_selector_schema,
    patch_selector_definitions_for_export,
)


def test_selector_schema_export_forbids_additional_properties() -> None:
    schema = _get_selector_schema(Selector, ResourceConfig)
    assert schema.get("additionalProperties") is False


def test_base_selector_runtime_accepts_extra_keys() -> None:
    """Shared ``Selector`` still accepts unknown keys at runtime."""
    raw = {"query": "true", "unexpected": 1}
    parsed = Selector.parse_obj(raw)
    assert parsed.query == "true"


def test_json_schema_export_patches_selector_definitions() -> None:
    schema = PortAppConfig.schema()
    patched = patch_selector_definitions_for_export(PortAppConfig, schema)
    selector_schema = patched.get("definitions", {}).get("Selector", {})
    assert selector_schema.get("additionalProperties") is False
