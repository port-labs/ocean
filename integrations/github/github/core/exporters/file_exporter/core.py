from typing import AsyncGenerator, Dict, List, Any, Optional, cast
from pathlib import Path
from urllib.parse import quote
import asyncio
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from port_ocean.core.ocean_types import ASYNC_GENERATOR_RESYNC_TYPE, RAW_ITEM
from loguru import logger
from github.core.options import FileContentOptions, FileSearchOptions
from github.clients.http.rest_client import GithubRestClient
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from .utils import (
    FileObject,
    decode_content,
    build_search_query,
    parse_content,
    validate_file_match,
)

FILE_REFERENCE_PREFIX = "file://"
MAX_FILE_SIZE = 1024 * 1024


class RestFileExporter(AbstractGithubExporter[GithubRestClient]):

    async def get_resource[
        ExporterOptionsT: FileContentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """
        Fetch the content of a file from a repository using the Contents API.
        """
        repo_name = options["repo_name"]
        file_path = options["file_path"]
        branch = options["branch"]

        resource = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/contents/{quote(file_path)}"
        logger.info(f"Fetching file: {file_path} from {repo_name}")

        response = await self.client.send_api_request(resource, params={"ref": branch})

        response_size = response["size"]
        content = None
        if response_size <= MAX_FILE_SIZE:
            content = decode_content(response["content"], response["encoding"])
        else:
            logger.warning(
                f"File {file_path} exceeds size limit ({response_size} bytes), skipping content processing"
            )

        return {**response, "content": content}

    async def get_paginated_resources[
        ExporterOptionsT: FileSearchOptions
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Search for files across repositories and fetch their content."""

        data = dict(options)
        filenames = cast(List[str], data["filenames"])
        path = cast(str, data["path"])
        repos = cast(Optional[List[str]], data.get("repos"))
        skip_parsing = cast(bool, data["skip_parsing"])
        branch = cast(str, data["branch"])

        if not repos:
            logger.warning("No repositories were provided, searching all repositories")

        for filename in filenames:
            query = build_search_query(
                filename=filename,
                path=path,
                organization=self.client.organization,
                repos=repos,
            )

            logger.info(f"Searching for files with query: {query}")

            async for search_results in self.client.send_paginated_request(
                f"{self.client.base_url}/search/code", params={"q": query}
            ):
                tasks = []
                typed_search_results = cast(dict[str, Any], search_results)
                search_results_items: list[dict[str, Any]] = typed_search_results[
                    "items"
                ]

                for result in search_results_items:
                    response_path = result["path"]

                    if not validate_file_match(response_path, filename, path):
                        logger.debug(
                            f"Skipping file {response_path} as it doesn't match expected patterns"
                        )
                        continue

                    tasks.append(
                        self.process_file(
                            result["repository"], result["path"], skip_parsing, branch
                        )
                    )

                async for file_results in stream_async_iterators_tasks(*tasks):
                    logger.debug(
                        f"Processed file results of {filenames} files from path: {path}"
                    )
                    yield [file_results]

    async def process_file(
        self,
        repository: Dict[str, Any],
        file_path: str,
        skip_parsing: bool,
        branch: str,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Process file content, optionally parsing it and handling nested structures.

        Args:
            file_info: File information from GitHub API response.
            skip_parsing: Whether to skip parsing the content.

        Returns:
            FileObject with processed content and metadata.
        """

        file_content = await self.get_resource(
            FileContentOptions(
                repo_name=repository["name"], file_path=file_path, branch=branch
            )
        )

        file_size = file_content["size"]
        file_path = file_content["path"]
        decoded_content = file_content.pop("content")

        if not decoded_content:
            result = FileObject(
                content=f"[File too large: {file_size} bytes]",
                repository=repository,
                branch=branch,
                metadata=file_content,
            )
            yield dict(result)
            return

        result = FileObject(
            content=decoded_content,
            repository=repository,
            branch=branch,
            metadata=file_content,
        )

        if not skip_parsing:
            parsed_content = parse_content(decoded_content, file_path)
            result = await self._resolve_file_references(
                parsed_content,
                str(Path(file_path).parent),
                branch,
                file_content,
                repository,
                branch,
            )

        yield dict(result)

    async def _resolve_file_references(
        self,
        content: Any,
        parent_dir: str,
        ref: str,
        file_metadata: Dict[str, Any],
        repo_metadata: Dict[str, Any],
        branch: str,
    ) -> FileObject:
        """
        Process parsed content and resolve file references.
        Returns processed FileObject with resolved references.
        """

        match content:
            case dict():
                result = await self._process_dict_content(
                    content,
                    parent_dir,
                    ref,
                    file_metadata,
                    repo_metadata,
                    branch,
                )
            case list():
                result = await self._process_list_content(
                    content,
                    parent_dir,
                    ref,
                    file_metadata,
                    repo_metadata,
                    branch,
                )
            case _:
                result = FileObject(
                    content=content,
                    repository=repo_metadata,
                    branch=branch,
                    metadata=file_metadata,
                )

        return result

    async def _process_dict_content(
        self,
        data: Dict[str, Any],
        parent_directory: str,
        branch: str,
        file_info: Dict[str, Any],
        repo_info: Dict[str, Any],
        branch_name: str,
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
            branch=branch_name,
            metadata=file_info,
        )

    async def _process_list_content(
        self,
        data: List[Dict[str, Any]],
        parent_directory: str,
        branch: str,
        file_info: Dict[str, Any],
        repo_info: Dict[str, Any],
        branch_name: str,
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
            branch=branch_name,
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

        file_content_response = await self.get_resource(
            FileContentOptions(repo_name=repository, file_path=file_path, branch=branch)
        )
        decoded_content = file_content_response["content"]
        file_size = file_content_response["size"]

        if not decoded_content:
            return f"[File too large: {file_size} bytes]"

        return parse_content(decoded_content, file_path)

    async def fetch_commit_diff(
        self, repo_name: str, before_sha: str, after_sha: str
    ) -> Dict[str, Any]:
        """
        Fetch the commit comparison data from GitHub API.
        """

        resource = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/compare/{before_sha}...{after_sha}"
        response = await self.client.send_api_request(resource)

        logger.info(f"Found {len(response['files'])} files in commit diff")

        return response
