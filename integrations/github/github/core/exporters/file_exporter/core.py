from typing import AsyncGenerator, Dict, List, Any, Optional, Tuple, cast
from pathlib import Path
from urllib.parse import quote
import asyncio
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.client_factory import create_github_client
from github.helpers.utils import GithubClientType
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
    FileObject,
    build_batch_file_query,
    decode_content,
    extract_file_index,
    get_graphql_file_metadata,
    match_files,
    parse_content,
)
from port_ocean.utils import cache


FILE_REFERENCE_PREFIX = "file://"


class RestFileExporter(AbstractGithubExporter[GithubRestClient]):

    @cache.cache_coroutine_result()
    async def get_repository_metadata(self, repo_name: str) -> Dict[str, Any]:
        url = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}"
        logger.info(f"Fetching metadata for repository: {repo_name}")

        response = await self.client.send_api_request(url)
        return response

    async def get_resource[
        ExporterOptionsT: FileContentOptions
    ](self, options: ExporterOptionsT) -> RAW_ITEM:
        """
        Fetch the content of a file from a repository using the Contents API.
        """
        repo_name = options["repo_name"]
        file_path = options["file_path"]
        branch = options.get("branch")

        resource = f"{self.client.base_url}/repos/{self.client.organization}/{repo_name}/contents/{quote(file_path)}"
        logger.info(f"Fetching file: {file_path} from {repo_name}@{branch}")

        response = await self.client.send_api_request(resource, params={"ref": branch})

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

    async def get_paginated_resources[
        ExporterOptionsT: List[ListFileSearchOptions]
    ](self, options: ExporterOptionsT) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Search for files across repositories and fetch their content."""

        graphql_files = []
        rest_files = []
        batch_results = []

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

        async for result in self.process_graphql_files(graphql_files):
            batch_results.extend(result)

        async for result in self.process_rest_api_files(rest_files):
            batch_results.extend(result)

        yield batch_results

    async def collect_matched_files(
        self, repo_name: str, file_patterns: List[FileSearchOptions]
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        graphql_files = []
        rest_files = []

        for spec in file_patterns:
            pattern = spec["path"]
            skip_parsing = spec["skip_parsing"]
            branch = spec["branch"]

            logger.debug(
                f"Processing pattern '{pattern}' on branch '{branch}' for {repo_name}"
            )
            tree_sha = await self.get_branch_tree_sha(repo_name, branch)
            tree = await self.get_tree_recursive(repo_name, tree_sha)

            matched = match_files(tree, pattern)

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

            decoded_content = file_data.pop("content")
            if decoded_content is None:
                logger.warning(f"File {file_path} has no content")
                continue

            repository = await self.get_repository_metadata(repo_name)

            file_obj = await self.process_file(
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
            repository_data = batch_result["file_data"]
            repository_obj = repository_data["repository"]

            repo_branch_files = [
                entry
                for entry in files
                if entry["repo_name"] == repo_name and entry["branch"] == branch
            ]
            file_paths = [entry["file_path"] for entry in repo_branch_files]
            file_metadata = {
                entry["file_path"]: entry["skip_parsing"] for entry in repo_branch_files
            }

            batch_files = []
            retrieved_files = {}

            for field_name, file_data in repository_obj.items():
                try:
                    content = file_data["text"]
                    retrieved_files[field_name] = file_data
                except (KeyError, TypeError):
                    repository_obj[field_name] = file_data

            logger.debug(f"Retrieved {len(retrieved_files)} files from GraphQL batch")

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

                file_obj = await self.process_file(
                    content=content,
                    repository=repository_obj,
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

            yield batch_files

    async def process_files_in_batches(
        self,
        matched_file_entries: List[Dict[str, Any]],
        batch_size: int = 5,
    ) -> AsyncGenerator[Dict[str, Any], None]:

        client = create_github_client(client_type=GithubClientType.GRAPHQL)

        grouped: Dict[Tuple[str, str], List[str]] = defaultdict(list)
        for entry in matched_file_entries:
            key = (entry["repo_name"], entry["branch"])
            grouped[key].append(entry["file_path"])

        for (repo_name, branch), paths in grouped.items():
            for i in range(0, len(paths), batch_size):
                batch = paths[i : i + batch_size]
                logger.debug(
                    f"Processing batch of {len(batch)} files for {repo_name}@{branch}"
                )

                query_payload = build_batch_file_query(
                    repo_name, client.organization, branch, batch
                )

                response = await client.send_api_request(
                    client.base_url, method="POST", json_data=query_payload
                )

                data = response.json()
                logger.info(f"Fetched {len(batch)} files from {repo_name}:{branch}")

                yield {
                    "repo": repo_name,
                    "branch": branch,
                    "file_data": data["data"],
                }

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

        result = FileObject(
            content=content,
            repository=repository,
            branch=branch,
            metadata={"path": file_path, **(metadata or {})},
        )

        if skip_parsing:
            logger.debug(f"Skipped parsing for {file_path}")
            return result

        parsed_content = parse_content(content, file_path)
        return await self._resolve_file_references(
            parsed_content,
            str(Path(file_path).parent),
            branch,
            result["metadata"],
            repository,
            branch,
        )

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
            logger.warning(
                f"Referenced file {file_path} is too large ({file_size} bytes)"
            )
            return ""

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

    async def get_branch_tree_sha(self, repo: str, branch: str) -> str:
        """Retrieve the full recursive tree for a given branch."""
        commit_url = f"{self.client.base_url}/repos/{self.client.organization}/{repo}/commits/{branch}"
        response = await self.client.send_api_request(commit_url)

        tree_sha = response["commit"]["tree"]["sha"]
        logger.info(f"Retrieved branch tree sha for {repo}@{branch}: {tree_sha[:8]}")

        return tree_sha

    async def get_tree_recursive(self, repo: str, sha: str) -> List[Dict[str, Any]]:
        """Retrieve the full recursive tree for a given branch."""
        tree_url = f"{self.client.base_url}/repos/{self.client.organization}/{repo}/git/trees/{sha}?recursive=1"
        response = await self.client.send_api_request(tree_url)

        tree_items = response["tree"]
        logger.info(f"Retrieved tree for {repo}@{sha[:8]}: {len(tree_items)} items")

        return tree_items
