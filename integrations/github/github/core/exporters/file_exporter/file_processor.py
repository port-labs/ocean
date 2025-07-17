from typing import Dict, List, Any, Optional, TYPE_CHECKING
from pathlib import Path
import asyncio
from loguru import logger
from github.core.options import FileContentOptions
from github.core.exporters.file_exporter.utils import FileObject, parse_content

if TYPE_CHECKING:
    from github.core.exporters.file_exporter.core import RestFileExporter

FILE_REFERENCE_PREFIX = "file://"


class FileProcessor:
    """Handles file reference resolution and content processing logic."""

    def __init__(self, exporter: "RestFileExporter"):
        self.exporter = exporter

    async def process_file(
        self,
        repository: Dict[str, Any],
        file_path: str,
        skip_parsing: bool,
        branch: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> FileObject:
        """
        Common content processor for GraphQL and REST paths.
        """
        file_name = Path(file_path).name
        file_parent_dir = str(Path(file_path).parent)

        result = FileObject(
            content=content,
            repository=repository,
            branch=branch,
            path=file_path,
            name=file_name,
            metadata=metadata or {},
        )

        if skip_parsing:
            logger.debug(f"Skipped parsing for {file_path}")
            return result

        parsed_content = parse_content(content, file_path)

        logger.info(f"Resolving file references for: {file_path}")

        return await self._resolve_file_references(
            parsed_content,
            file_parent_dir,
            file_path,
            file_name,
            branch,
            result["metadata"],
            repository,
        )

    async def _resolve_file_references(
        self,
        content: Any,
        parent_dir: str,
        file_path: str,
        file_name: str,
        branch: str,
        file_metadata: Dict[str, Any],
        repo_metadata: Dict[str, Any],
    ) -> FileObject:
        """
        Process parsed content and resolve file references.
        Returns processed FileObject with resolved references.
        """

        match content:
            case dict():
                logger.debug("Content is a dictionary. Processing dict content.")
                result = await self._process_dict_content(
                    content,
                    parent_dir,
                    file_path,
                    file_name,
                    branch,
                    file_metadata,
                    repo_metadata,
                )
            case list():
                logger.debug("Content is a list. Processing list content.")
                result = await self._process_list_content(
                    content,
                    parent_dir,
                    file_path,
                    file_name,
                    branch,
                    file_metadata,
                    repo_metadata,
                )
            case _:
                logger.info("Content is not a dictionary or list. Returning as is.")
                result = FileObject(
                    content=content,
                    repository=repo_metadata,
                    branch=branch,
                    path=file_path,
                    name=file_name,
                    metadata=file_metadata,
                )

        return result

    async def _process_dict_content(
        self,
        data: Dict[str, Any],
        parent_directory: str,
        file_path: str,
        file_name: str,
        branch: str,
        file_info: Dict[str, Any],
        repo_info: Dict[str, Any],
    ) -> FileObject:
        """Process dictionary items and resolve file references."""
        tasks = [
            self._process_file_value(value, parent_directory, repo_info["name"], branch)
            for value in data.values()
        ]
        processed_values = await asyncio.gather(*tasks)

        result = dict(zip(data.keys(), processed_values))

        return FileObject(
            content=result,
            repository=repo_info,
            branch=branch,
            path=file_path,
            name=file_name,
            metadata=file_info,
        )

    async def _process_list_content(
        self,
        data: List[Dict[str, Any]],
        parent_directory: str,
        file_path: str,
        file_name: str,
        branch: str,
        file_info: Dict[str, Any],
        repo_info: Dict[str, Any],
    ) -> FileObject:
        """Process each dict item in the list concurrently, resolving file references."""

        async def process_item(item: Dict[str, Any]) -> Dict[str, Any]:
            keys = list(item.keys())
            values = await asyncio.gather(
                *[
                    self._process_file_value(
                        v, parent_directory, repo_info["name"], branch
                    )
                    for v in item.values()
                ]
            )
            return dict(zip(keys, values))

        processed_items = await asyncio.gather(*[process_item(obj) for obj in data])

        return FileObject(
            content=processed_items,
            repository=repo_info,
            branch=branch,
            path=file_path,
            name=file_name,
            metadata=file_info,
        )

    async def _process_file_value(
        self,
        value: Any,
        parent_directory: str,
        repository: str,
        branch: str,
    ) -> Any:
        if not isinstance(value, str) or not value.startswith(FILE_REFERENCE_PREFIX):
            logger.debug(
                f"Value is not a string or does not start with {FILE_REFERENCE_PREFIX}, returning as is - {value}"
            )
            return value

        file_meta = Path(value.replace(FILE_REFERENCE_PREFIX, ""))
        file_path = (
            f"{parent_directory}/{file_meta}"
            if parent_directory != "."
            else str(file_meta)
        )

        logger.info(
            f"Processing file reference: {value} -> {file_path} in {repository}@{branch}"
        )

        file_content_response = await self.exporter.get_resource(
            FileContentOptions(repo_name=repository, file_path=file_path, branch=branch)
        )
        decoded_content = file_content_response.get("content")
        if not decoded_content:
            logger.warning(f"File {file_path} has no content")
            return ""

        return parse_content(decoded_content, file_path)
