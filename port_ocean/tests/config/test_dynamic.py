from typing import Any

import pytest
from pydantic import ValidationError

from port_ocean.config.base import BaseOceanModel
from port_ocean.config.dynamic import default_config_factory


def test_factory_builds_url_fields_as_strings_without_trailing_slash() -> None:
    # Arrange
    model_cls = default_config_factory(
        [{"name": "hostUrl", "type": "url", "required": True, "sensitive": False}]
    )

    # Act
    config: Any = model_cls(host_url="https://example.com/")

    # Assert
    assert config.host_url == "https://example.com"
    assert isinstance(config.host_url, str)
    assert config.model_dump(mode="json")["host_url"] == "https://example.com"


def test_factory_parses_json_object_and_array_strings() -> None:
    # Arrange
    model_cls = default_config_factory(
        [
            {"name": "headers", "type": "object", "required": False},
            {"name": "tags", "type": "array", "required": False},
        ]
    )

    # Act
    config: Any = model_cls(headers='{"Authorization": "Bearer x"}', tags='["a", "b"]')

    # Assert
    assert config.headers == {"Authorization": "Bearer x"}
    assert config.tags == ["a", "b"]


def test_factory_marks_sensitive_fields() -> None:
    # Arrange
    model_cls = default_config_factory(
        [
            {
                "name": "token",
                "type": "string",
                "required": True,
                "sensitive": True,
            }
        ]
    )

    # Act
    config = model_cls(token="secret-token")

    # Assert
    assert isinstance(config, BaseOceanModel)
    assert config.get_sensitive_fields_data() == {"secret-token"}


def test_factory_rejects_unknown_type() -> None:
    # Act + Assert
    with pytest.raises(ValueError, match="Unknown type"):
        default_config_factory([{"name": "field", "type": "float", "required": False}])


def test_factory_rejects_invalid_url() -> None:
    # Arrange
    model_cls = default_config_factory(
        [{"name": "host", "type": "url", "required": True}]
    )

    # Act + Assert
    with pytest.raises(ValidationError):
        model_cls(host="/")
