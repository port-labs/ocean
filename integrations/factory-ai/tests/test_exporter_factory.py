import pytest

from factory_ai.core.exporters.computer import ComputerExporter
from factory_ai.core.exporters.computer.models import ListComputerOptions
from factory_ai.core.exporters.environment import EnvironmentExporter
from factory_ai.core.exporters.environment.models import ListEnvironmentOptions
from factory_ai.exporter_factory import get_exporter_metadata
from factory_ai.kinds import ObjectKind


def test_get_exporter_metadata_environment() -> None:
    metadata = get_exporter_metadata(ObjectKind.ENVIRONMENT)
    assert metadata.exporter is EnvironmentExporter
    assert metadata.list_options_model is ListEnvironmentOptions


def test_get_exporter_metadata_computer() -> None:
    metadata = get_exporter_metadata(ObjectKind.COMPUTER)
    assert metadata.exporter is ComputerExporter
    assert metadata.list_options_model is ListComputerOptions


def test_get_exporter_metadata_unimplemented_kind() -> None:
    with pytest.raises(NotImplementedError, match="session"):
        get_exporter_metadata(ObjectKind.SESSION)
