from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from factory_ai.core.exporters.abstract_exporter import AbstractFactoryExporter
from factory_ai.core.exporters.computer import ComputerExporter
from factory_ai.core.exporters.computer.models import ListComputerOptions
from factory_ai.core.exporters.environment import EnvironmentExporter
from factory_ai.core.exporters.environment.models import ListEnvironmentOptions
from factory_ai.core.exporters.session import SessionExporter
from factory_ai.core.exporters.session.models import ListSessionOptions
from factory_ai.core.exporters.user import UserExporter
from factory_ai.core.exporters.user.models import ListUserOptions
from factory_ai.kinds import ObjectKind


@dataclass(frozen=True)
class ExporterMetadata:
    exporter: type[AbstractFactoryExporter[Any, Any]]
    list_options_model: type[BaseModel]


kind_to_exporter_metadata: dict[ObjectKind, ExporterMetadata] = {
    ObjectKind.ENVIRONMENT: ExporterMetadata(
        EnvironmentExporter,
        ListEnvironmentOptions,
    ),
    ObjectKind.COMPUTER: ExporterMetadata(
        ComputerExporter,
        ListComputerOptions,
    ),
    ObjectKind.SESSION: ExporterMetadata(
        SessionExporter,
        ListSessionOptions,
    ),
    ObjectKind.USER: ExporterMetadata(
        UserExporter,
        ListUserOptions,
    ),
}


def get_exporter_metadata(kind: ObjectKind) -> ExporterMetadata:
    metadata = kind_to_exporter_metadata.get(kind)
    if metadata is None:
        raise NotImplementedError(
            f"Exporter for kind {kind.value!r} is not implemented yet"
        )
    return metadata
