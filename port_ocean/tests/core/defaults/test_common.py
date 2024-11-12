import pytest
import json
from unittest.mock import patch
from pathlib import Path
from port_ocean.core.handlers.port_app_config.models import PortAppConfig
from port_ocean.core.defaults.common import (
    get_port_integration_defaults,
    Defaults,
)


@pytest.fixture
def setup_mock_directories(tmp_path: Path) -> tuple[Path, Path, Path]:
    # Create .port/resources with sample files
    default_dir = tmp_path / ".port/resources"
    default_dir.mkdir(parents=True, exist_ok=True)

    # Create mock JSON and YAML files with expected content
    (default_dir / "blueprints.json").write_text(
        json.dumps(
            [
                {
                    "identifier": "mock-identifier",
                    "title": "mock-title",
                    "icon": "mock-icon",
                    "schema": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}},
                    },
                }
            ]
        )
    )
    (default_dir / "port-app-config.json").write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "kind": "mock-kind",
                        "selector": {"query": "true"},
                        "port": {
                            "entity": {
                                "mappings": {
                                    "identifier": ".id",
                                    "title": ".title",
                                    "blueprint": '"mock-identifier"',
                                }
                            }
                        },
                    }
                ]
            }
        )
    )

    # Create .port/custom_resources with different sample files
    custom_resources_dir = tmp_path / ".port/custom_resources"
    custom_resources_dir.mkdir(parents=True, exist_ok=True)

    # Create mock JSON and YAML files with expected content
    (custom_resources_dir / "blueprints.json").write_text(
        json.dumps(
            [
                {
                    "identifier": "mock-custom-identifier",
                    "title": "mock-custom-title",
                    "icon": "mock-custom-icon",
                    "schema": {
                        "type": "object",
                        "properties": {"key": {"type": "string"}},
                    },
                }
            ]
        )
    )
    (custom_resources_dir / "port-app-config.json").write_text(
        json.dumps(
            {
                "resources": [
                    {
                        "kind": "mock-custom-kind",
                        "selector": {"query": "true"},
                        "port": {
                            "entity": {
                                "mappings": {
                                    "identifier": ".id",
                                    "title": ".title",
                                    "blueprint": '"mock-custom-identifier"',
                                }
                            }
                        },
                    }
                ]
            }
        )
    )

    # Define the non-existing directory path
    non_existing_dir = tmp_path / ".port/do_not_exist"

    return default_dir, custom_resources_dir, non_existing_dir


def test_custom_defaults_dir_used_if_valid(
    setup_mock_directories: tuple[Path, Path, Path]
) -> None:
    # Arrange
    _, custom_resources_dir, _ = setup_mock_directories

    with (
        patch("port_ocean.core.defaults.common.is_valid_dir") as mock_is_valid_dir,
        patch(
            "pathlib.Path.iterdir",
            return_value=custom_resources_dir.iterdir(),
        ),
    ):
        mock_is_valid_dir.side_effect = lambda path: path == custom_resources_dir

        # Act
        defaults = get_port_integration_defaults(
            port_app_config_class=PortAppConfig,
            custom_defaults_dir=".port/custom_resources",
            base_path=custom_resources_dir.parent.parent,
        )

        # Assert
        assert isinstance(defaults, Defaults)
        assert defaults.blueprints[0].get("identifier") == "mock-custom-identifier"
        assert defaults.port_app_config is not None
        assert defaults.port_app_config.resources[0].kind == "mock-custom-kind"


def test_fallback_to_default_dir_if_custom_dir_invalid(
    setup_mock_directories: tuple[Path, Path, Path]
) -> None:
    resources_dir, _, non_existing_dir = setup_mock_directories

    # Arrange
    with (
        patch("port_ocean.core.defaults.common.is_valid_dir") as mock_is_valid_dir,
        patch("pathlib.Path.iterdir", return_value=resources_dir.iterdir()),
    ):

        mock_is_valid_dir.side_effect = lambda path: path == resources_dir

        # Act
        custom_defaults_dir = str(non_existing_dir.relative_to(resources_dir.parent))
        defaults = get_port_integration_defaults(
            port_app_config_class=PortAppConfig,
            custom_defaults_dir=custom_defaults_dir,
            base_path=resources_dir.parent.parent,
        )

        # Assert
        assert isinstance(defaults, Defaults)
        assert defaults.blueprints[0].get("identifier") == "mock-identifier"
        assert defaults.port_app_config is not None
        assert defaults.port_app_config.resources[0].kind == "mock-kind"


def test_default_resources_path_does_not_exist() -> None:
    # Act
    defaults = get_port_integration_defaults(port_app_config_class=PortAppConfig)

    # Assert
    assert defaults is None
