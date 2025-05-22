from typing import Dict, Type
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.core.exporters.repository_exporter import RestRepositoryExporter
from github.helpers.utils import ObjectKind
from github.clients.base_client import AbstractGithubClient


class ExporterFactory:
    """Factory to create exporters based on resource kind."""

    def __init__(self) -> None:
        self._registry: Dict[
            ObjectKind, Type[AbstractGithubExporter[AbstractGithubClient]]
        ] = {
            ObjectKind.REPOSITORY: RestRepositoryExporter,
            # Add more mappings as needed
        }

    def get_exporter(
        self, kind: ObjectKind
    ) -> Type[AbstractGithubExporter[AbstractGithubClient]]:
        """Get an exporter for the given kind."""
        try:
            exporter_class = self._registry[kind]
        except KeyError:
            raise ValueError(f"Unsupported resource kind: {kind}")

        return exporter_class
