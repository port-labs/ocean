from typing import Any

from port_ocean.core.handlers.port_app_config.models import PortAppConfig


def _resource(enable_delete: bool | None = None) -> dict[str, Any]:
    resource: dict[str, Any] = {
        "kind": "namespace",
        "selector": {"query": "true"},
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".metadata.uid",
                    "title": ".metadata.name",
                    "blueprint": '"namespace"',
                }
            }
        },
    }
    if enable_delete is not None:
        resource["enableDelete"] = enable_delete
    return resource


def test_enable_delete_defaults_true_when_omitted() -> None:
    config = PortAppConfig.parse_obj({"resources": [_resource()]})
    assert config.resources[0].enable_delete is True


def test_enable_delete_omitted_absent_from_to_request() -> None:
    """Omit → default true in-memory, but key stays absent in to_request (exclude_unset)."""
    config = PortAppConfig.parse_obj({"resources": [_resource()]})
    assert config.resources[0].enable_delete is True
    payload = config.to_request()
    assert "enableDelete" not in payload["resources"][0]


def test_enable_delete_false_round_trips_in_to_request() -> None:
    config = PortAppConfig.parse_obj({"resources": [_resource(enable_delete=False)]})
    assert config.resources[0].enable_delete is False
    payload = config.to_request()
    assert payload["resources"][0]["enableDelete"] is False


def test_enable_delete_false_round_trips_in_dsp_lifecycle_mapping() -> None:
    config = PortAppConfig.parse_obj({"resources": [_resource(enable_delete=False)]})
    mapping = config.to_dsp_lifecycle_mapping()
    assert mapping["resources"][0]["enableDelete"] is False
    # mappings stay list-shaped for DSP lifecycle
    assert isinstance(mapping["resources"][0]["port"]["entity"]["mappings"], list)


def test_enable_delete_rejects_non_boolean() -> None:
    import pytest
    from pydantic.v1 import ValidationError

    with pytest.raises(ValidationError):
        PortAppConfig.parse_obj({"resources": [_resource(enable_delete="false")]})  # type: ignore[arg-type]


def test_enable_delete_rejects_null() -> None:
    """null is not omit — reject so callers omit the key for default true."""
    import pytest
    from pydantic.v1 import ValidationError

    resource = _resource()
    resource["enableDelete"] = None
    with pytest.raises(ValidationError):
        PortAppConfig.parse_obj({"resources": [resource]})
