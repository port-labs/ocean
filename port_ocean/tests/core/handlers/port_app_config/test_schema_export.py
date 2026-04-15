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


def _extract_selector_ref(property_schema: dict[str, object]) -> str:
    """Return the ``$ref`` string from a selector property schema fragment."""
    direct = property_schema.get("$ref")
    if isinstance(direct, str):
        return direct
    all_of = property_schema.get("allOf")
    if isinstance(all_of, list) and all_of and isinstance(all_of[0], dict):
        nested = all_of[0].get("$ref")
        if isinstance(nested, str):
            return nested
    raise AssertionError("selector property does not reference a definition")
