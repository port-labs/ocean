from typing import AsyncGenerator, Dict, List, Any, Tuple, cast
from urllib.parse import quote
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.client_factory import create_github_client
from github.helpers.utils import GithubClientType, IgnoredError
from port_ocean.core.ocean_types import (
    ASYNC_GENERATOR_RESYNC_TYPE,
    RAW_ITEM,
)
from loguru import logger
from github.core.options import (
    FileContentOptions,
    FileSearchOptions,
    ListFileSearchOptions,
)
from github.clients.http.rest_client import GithubRestClient
from collections import defaultdict

from github.core.exporters.file_exporter.utils import (
    MAX_FILE_SIZE,
    build_batch_file_query,
    decode_content,
    extract_file_index,
    extract_file_paths_and_metadata,
    filter_github_tree_entries_by_pattern,
    get_graphql_file_metadata,
)
from port_ocean.utils import cache
from github.core.exporters.file_exporter.file_processor import FileProcessor


class RestFileExporter(AbstractGithubExporter[GithubRestClient]):
    _IGNORED_ERRORS = [
        IgnoredError(status=409, message="empty repository"),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.file_processor = FileProcessor(self)

    @cache.cache_coroutine_result()
    async def get_repository_metadata(self, repo_name: str) -> Dict[str, Any]:
        url = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}"
        logger.info(f"Fetching metadata for repository: {repo_name}")

        return await self.client.send_api_request(url)

    async def get_resource[ExporterOptionsT: FileContentOptions](
        self, options: ExporterOptionsT
    ) -> RAW_ITEM:
        """
        Fetch the content of a file from a repository using the Contents API.
        """
        repo_name = options["repo_name"]
        file_path = options["file_path"]
        branch = options.get("branch")

        resource = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/contents/{quote(file_path)}"
        logger.info(f"Fetching file: {file_path} from {repo_name}@{branch}")

        response = await self.client.send_api_request(resource, params={"ref": branch})
        if not response:
            logger.warning(f"File {file_path} not found in {repo_name}@{branch}")
            return {}

        response_size = response["size"]
        content = None
        if response_size <= MAX_FILE_SIZE:
            content = decode_content(response["content"], response["encoding"])
            logger.debug(
                f"Successfully decoded file {file_path} ({response_size} bytes)"
            )
        else:
            logger.warning(
                f"File {file_path} exceeds size limit ({response_size} bytes > {MAX_FILE_SIZE}), skipping content processing"
            )

        return {**response, "content": content}

    async def get_paginated_resources[ExporterOptionsT: List[ListFileSearchOptions]](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Search for files across repositories and fetch their content."""

        graphql_files = []
        rest_files = []

        for repo_options in options:
            data = dict(repo_options)
            repo_name = cast(str, data["repo_name"])
            files = cast(List[FileSearchOptions], data["files"])

            logger.debug(
                f"Processing repository {repo_name} with {len(files)} file patterns"
            )

            gql, rest = await self.collect_matched_files(repo_name, files)
            graphql_files.extend(gql)
            rest_files.extend(rest)

        logger.info(f"Processing {len(graphql_files)} GraphQL files")
        async for result in self.process_graphql_files(graphql_files):
            yield result

        logger.info(f"Processing {len(rest_files)} REST API files")
        async for result in self.process_rest_api_files(rest_files):
            yield result

    async def collect_matched_files(
        self, repo_name: str, file_patterns: List[FileSearchOptions]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        graphql_files = []
        rest_files = []

        for spec in file_patterns:
            pattern = spec["path"]
            skip_parsing = spec["skip_parsing"]

            repo_obj = await self.get_repository_metadata(repo_name)
            branch = spec.get("branch") or repo_obj["default_branch"]

            logger.debug(
                f"Processing pattern '{pattern}' on branch '{branch}' for {repo_name}"
            )
            tree = await self.get_tree_recursive(repo_name, branch)

            matched = filter_github_tree_entries_by_pattern(tree, pattern)

            logger.info(
                f"Matched {len(matched)} files in {repo_name} with pattern '{pattern}'"
            )

            for match in matched:
                path = match["path"]
                fetch_method = match["fetch_method"]

                file_info = {
                    "repo_name": repo_name,
                    "file_path": path,
                    "skip_parsing": skip_parsing,
                    "branch": branch,
                }

                logger.debug(f"File {path} will be fetched via {fetch_method}")

                if fetch_method == GithubClientType.GRAPHQL:
                    graphql_files.append(file_info)
                else:
                    rest_files.append(file_info)

        return graphql_files, rest_files

    async def process_rest_api_files(
        self, files: List[Dict[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        batch_files = []
        for file_entry in files:
            repo_name = file_entry["repo_name"]
            file_path = file_entry["file_path"]
            skip_parsing = file_entry["skip_parsing"]
            branch = file_entry["branch"]

            file_data = await self.get_resource(
                FileContentOptions(
                    repo_name=repo_name,
                    file_path=file_path,
                    branch=branch,
                )
            )

            decoded_content = file_data.pop("content", None)
            if decoded_content is None:
                logger.warning(f"File {file_path} has no content")
                continue

            repository = await self.get_repository_metadata(repo_name)

            file_obj = await self.file_processor.process_file(
                content=decoded_content,
                repository=repository,
                file_path=file_path,
                skip_parsing=skip_parsing,
                branch=branch,
                metadata=file_data,
            )

            batch_files.append(dict(file_obj))
            logger.debug(f"Successfully processed REST file: {file_path}")

        yield batch_files

    async def process_graphql_files(
        self, files: List[Dict[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch_result in self.process_files_in_batches(files):
            repo_name = batch_result["repo"]
            branch = batch_result["branch"]
            retrieved_files = batch_result["file_data"]["repository"]
            repository_metadata = await self.get_repository_metadata(repo_name)

            logger.debug(f"Retrieved {len(retrieved_files)} files from GraphQL batch")

            file_paths, file_metadata = extract_file_paths_and_metadata(
                batch_result["batch_files"]
            )

            batch_files = await self._process_retrieved_graphql_files(
                retrieved_files,
                file_paths,
                file_metadata,
                repository_metadata,
                repo_name,
                branch,
            )

            yield batch_files

    async def process_files_in_batches(
        self,
        matched_file_entries: List[Dict[str, Any]],
        batch_size: int = 7,
    ) -> AsyncGenerator[Dict[str, Any], None]:
        # Using batch_size = 7 to balance throughput and response size.
        # Each file blob can be up to 100KB; 7 files keeps payloads safely under ~700KB,
        # reducing risk of GraphQL timeouts while improving efficiency over smaller batches.

        client = create_github_client(client_type=GithubClientType.GRAPHQL)

        grouped: Dict[Tuple[str, str], List[Dict[str, Any]]] = defaultdict(list)
        for entry in matched_file_entries:
            key = (entry["repo_name"], entry["branch"])
            grouped[key].append(entry)

        for (repo_name, branch), entries in grouped.items():
            for i in range(0, len(entries), batch_size):
                batch_files = entries[i : i + batch_size]
                logger.debug(
                    f"Processing batch of {len(batch_files)} files for {repo_name}@{branch}"
                )

                batch_file_paths = [entry["file_path"] for entry in batch_files]

                query_payload = build_batch_file_query(
                    repo_name, client.organization, branch, batch_file_paths
                )

                response = await client.send_api_request(
                    client.base_url, method="POST", json_data=query_payload
                )

                logger.info(
                    f"Fetched {len(batch_files)} files from {repo_name}:{branch}"
                )

                yield {
                    "repo": repo_name,
                    "branch": branch,
                    "file_data": response["data"],
                    "batch_files": batch_files,
                }

    async def _process_retrieved_graphql_files(
        self,
        retrieved_files: Dict[str, Any],
        file_paths: List[str],
        file_metadata: Dict[str, bool],
        repository_metadata: Dict[str, Any],
        repo_name: str,
        branch: str,
    ) -> List[Dict[str, Any]]:
        batch_files = []

        for field_name, file_data in retrieved_files.items():
            file_index = extract_file_index(field_name)

            if file_index is None or file_index >= len(file_paths):
                logger.warning(
                    f"Unexpected field name format: '{field_name}' in {repo_name}@{branch}"
                )
                continue

            file_path = file_paths[file_index]
            content = file_data["text"]
            size = file_data.get("byteSize", 0)
            skip_parsing = file_metadata.get(file_path, False)

            if not content:
                logger.warning(f"File {file_path} has no content")
                continue

            file_obj = await self.file_processor.process_file(
                content=content,
                repository=repository_metadata,
                file_path=file_path,
                skip_parsing=skip_parsing,
                branch=branch,
                metadata=get_graphql_file_metadata(
                    self.client.base_url,
                    self.client.organization,
                    repo_name,
                    branch,
                    file_path,
                    size,
                ),
            )

            batch_files.append(dict(file_obj))

        return batch_files

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

    async def get_tree_recursive(self, repo: str, branch: str) -> List[Dict[str, Any]]:
        """Retrieve the full recursive tree for a given branch."""
        tree_url = f"{self.client.base_url}/repos/{self.client.organization}/{repo}/git/trees/{branch}?recursive=1"
        response = await self.client.send_api_request(
            tree_url, ignored_errors=self._IGNORED_ERRORS
        )
        if not response:
            logger.warning(f"Did not retrieve tree from {repo}@{branch}")
            return []

        tree_items = response["tree"]
        logger.info(f"Retrieved tree for {repo}@{branch}: {len(tree_items)} items")

        return tree_items
