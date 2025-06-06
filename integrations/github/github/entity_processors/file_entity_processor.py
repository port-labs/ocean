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
        self, repo_name: str, ref: str, file_path: str
    ) -> Optional[Any]:
        """Helper method to fetch and process file content."""

        rest_client = create_github_client()
        exporter = RestFileExporter(rest_client)

        file_content_response = await exporter.get_resource(
            FileContentOptions(repo_name=repo_name, file_path=file_path, ref=ref)
        )
        decoded_content = file_content_response["content"]
        if not decoded_content:
            return f"[File too large: {file_content_response['size']} bytes]"
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
        repo_name = repo_data["name"]
        ref = repo_data["default_branch"]

        # TODO: Handle monorepo case

        file_path = pattern.replace(self.prefix, "")

        logger.info(
            f"Searching for file {file_path} in Repository {repo_name}, ref {ref}"
        )
        return await self._get_file_content(repo_name, ref, file_path)
