from typing import Literal

import pytest
from pydantic import ValidationError

from port_ocean.core.handlers.port_app_config.models import (
    PortAppConfig,
    PortResourceConfig,
    ResourceConfig,
    Selector,
)
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


def test_patches_correct_definition_when_selector_names_collide() -> None:
    """Two selector models with the same __name__ must each get patched
    under the definition key that the schema actually references."""

    class AzureDevopsSelector(Selector):
        include_comments: bool = False

    class AzureDevopsRepositoryResourceConfig(ResourceConfig):
        kind: Literal["repository"]
        selector: AzureDevopsSelector
        port: PortResourceConfig

    class AzureDevopsWorkItemResourceConfig(ResourceConfig):
        kind: Literal["work_item"]
        port: PortResourceConfig

        class AzureDevopsSelector(Selector):
            include_related_links: bool = False

        selector: AzureDevopsSelector

    class AzureDevopsPortAppConfig(PortAppConfig):
        resources: list[
            AzureDevopsRepositoryResourceConfig | AzureDevopsWorkItemResourceConfig
        ]

    schema = AzureDevopsPortAppConfig.schema()
    patched = patch_selector_definitions_for_export(AzureDevopsPortAppConfig, schema)
    definitions = patched.get("definitions", {})

    repo_ref = _extract_selector_ref(
        definitions["AzureDevopsRepositoryResourceConfig"]["properties"]["selector"]
    )
    wi_ref = _extract_selector_ref(
        definitions["AzureDevopsWorkItemResourceConfig"]["properties"]["selector"]
    )
    repo_key = repo_ref.split("/")[-1]
    wi_key = wi_ref.split("/")[-1]

    assert repo_key != wi_key, "Pydantic should disambiguate same-named selectors"
    assert definitions[repo_key].get("additionalProperties") is False
    assert definitions[wi_key].get("additionalProperties") is False
