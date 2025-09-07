from loguru import logger
from typing import Any, Dict, List

from github.clients.rest_client import RestClient
from github.exporters.base import BaseExporter
from github.kind.object_kind import ObjectKind
from github.settings import SETTINGS


class RepositoryExporter(BaseExporter):
    """Exporter for GitHub Repositories"""

    KIND = ObjectKind.REPOSITORY.value

    def __init__(self) -> None:
        self.client = RestClient()
        self.org = SETTINGS.organization or ""
        self.user = SETTINGS.user or ""

    async def export(self) -> List[Dict[str, Any]]:
        """
        Export repositories from GitHub API

        Returns:
            List of repository dicts as returned by GitHub API
        """
        try:
            logger.info(
                f"[{self.__class__.__name__}] kind={self.KIND} Starting export from GitHub API"
            )

            base_path = self.get_base_path()
            response = await self.client.get(f"{base_path}/repos")
            logger.info(
                f"[{self.__class__.__name__}] kind={self.KIND} API status={response.status_code}"
            )
            response.raise_for_status()

            repositories = response.json()
            return repositories if isinstance(repositories, list) else []

        except Exception as e:
            logger.error(
                f"[{self.__class__.__name__}] kind={self.KIND} Failed to export repositories | error={e}",
                exc_info=True,
            )
            return []


