import os
from typing import Any, Optional
from loguru import logger
from port_ocean.core.handlers import JQEntityProcessor
from github.clients.client_factory import create_github_client
from github.core.options import FileContentOptions
from github.core.exporters.file_exporter.core import RestFileExporter


FILE_PROPERTY_PREFIX = "file://"


class FileEntityProcessor(JQEntityProcessor):
    prefix = FILE_PROPERTY_PREFIX

    async def _get_file_content(
        self,
        organization: str,
        repo_name: str,
        file_path: str,
        branch: Optional[str] = None,
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""

        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)

        file_content_response = await exporter.get_resource(
            FileContentOptions(
                organization=organization,
                repo_name=repo_name,
                file_path=file_path,
                branch=branch,
            )
        )
        decoded_content = file_content_response["content"]
        if not decoded_content:
            logger.info(f"File too large, size - {file_content_response['size']} bytes")
            return None

        logger.info(
            f"File content fetched, size - {file_content_response['size']} bytes"
        )
        return decoded_content

    async def _search(self, data: dict[str, Any], pattern: str) -> Any:
        """
        Search for a file in the repository and return its content.

        Args:
            data (dict[str, Any]): The data containing the repository information
            pattern (str): The pattern to search for (e.g. "file://path/to/file.yaml")

            For monorepo, the data should contain a "repo" key and a "folder" key with the repository information.
            For non-monorepo, the data should contain the repository information directly.

        Returns:
            Any: The raw or parsed content of the file
        """

        repo_data = data.get("repository", data)
        is_monorepo = "repository" in data

        repo_name = repo_data["name"]
        organization = repo_data["owner"]["login"]
        ref = data["branch"] if is_monorepo else repo_data.get("default_branch")

        base_pattern = pattern.replace(self.prefix, "")
        file_path = (
            os.path.join(
                os.path.dirname(data["metadata"]["path"]), base_pattern
            ).replace(os.sep, "/")
            if is_monorepo
            else base_pattern
        )

        logger.info(
            f"Searching for file {file_path} in Repository {repo_name}, ref {ref}"
        )

        return await self._get_file_content(organization, repo_name, file_path, ref)
