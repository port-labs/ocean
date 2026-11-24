import pytest

from factory_ai.core.exporters.computer import ComputerExporter
from factory_ai.core.exporters.computer.models import ListComputerOptions
from factory_ai.core.exporters.environment import EnvironmentExporter
from factory_ai.core.exporters.environment.models import ListEnvironmentOptions
from factory_ai.core.exporters.session import SessionExporter
from factory_ai.core.exporters.session.models import ListSessionOptions
from factory_ai.core.exporters.user import UserExporter
from factory_ai.core.exporters.user.models import ListUserOptions
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


def test_get_exporter_metadata_user() -> None:
    metadata = get_exporter_metadata(ObjectKind.USER)
    assert metadata.exporter is UserExporter
    assert metadata.list_options_model is ListUserOptions


def test_get_exporter_metadata_session() -> None:
    metadata = get_exporter_metadata(ObjectKind.SESSION)
    assert metadata.exporter is SessionExporter
    assert metadata.list_options_model is ListSessionOptions


def test_get_exporter_metadata_unimplemented_kind() -> None:
    with pytest.raises(NotImplementedError, match="automation"):
        get_exporter_metadata(ObjectKind.AUTOMATION)
