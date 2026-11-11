from datetime import datetime, timezone
from typing import (
    Any,
    AsyncGenerator,
    Dict,
    List,
    Optional,
    Tuple,
    cast,
)
from urllib.parse import quote
import httpx
from github.core.exporters.abstract_exporter import AbstractGithubExporter
from github.clients.client_factory import create_github_client_for_org
from github.helpers.repository_change import RepositoryChange
from github.helpers.utils import GithubClientType, IgnoredError, get_repository_metadata
from github.helpers.exceptions import GitHubTreeFetchError
from port_ocean.exceptions.core import OceanAbortException
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

from port_ocean.utils.cache import cache_coroutine_result
from github.core.exporters.file_exporter.utils import (
    GITHUB_COMPARE_FILE_CAP,
    COMPARE_BASE_IS_ANCESTOR_STATUSES,
    build_batch_file_query,
    decode_content,
    extract_file_index,
    extract_file_paths_and_metadata,
    filter_github_tree_entries_by_pattern,
    get_graphql_file_metadata,
    match_file_path_against_glob_pattern,
)
from github.core.exporters.file_exporter.file_processor import (
    FileProcessor,
    FileResponseValidator,
)


# (organization, repo_name, branch, pattern) -> matched tree entries
class RestFileExporter(AbstractGithubExporter[GithubRestClient]):
    _IGNORED_ERRORS = [
        IgnoredError(status=404, message="Resource not found at endpoint"),
        IgnoredError(status=409, message="empty repository"),
    ]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.file_processor = FileProcessor(self)

    async def get_resource[ExporterOptionsT: FileContentOptions](
        self, options: ExporterOptionsT
    ) -> Optional[RAW_ITEM]:
        """
        Fetch the content of a file from a repository using the Contents API.
        """
        organization = options["organization"]
        repo_name = options["repo_name"]
        file_path = options["file_path"]
        branch = options.get("branch")

        resource = f"{self.client.base_url}/repos/{organization}/{repo_name}/contents/{quote(file_path)}"
        logger.info(
            f"Fetching file: {file_path} from {repo_name}@{branch} from {organization}"
        )

        response = await self.client.send_api_request(resource, params={"ref": branch})
        if not response:
            logger.warning(
                f"File {file_path} not found in {repo_name}@{branch} from {organization}"
            )
            return None

        validator = FileResponseValidator(
            file_path=file_path,
            organization=organization,
            repo_name=repo_name,
            branch=str(branch),
        )
        if error := validator.validate(response):
            logger.warning(error)
            return {**response, "content": None}

        content = decode_content(response["content"], response["encoding"])
        logger.debug(
            f"Successfully decoded file {file_path} ({response['size']} bytes) from {organization}/{repo_name} and branch {branch}"
        )

        return {**response, "content": content}

    async def get_paginated_resources[ExporterOptionsT: List[ListFileSearchOptions]](
        self, options: ExporterOptionsT
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        """Files matching the patterns, with content.

        A repository's ``changed_since`` limits it to files changed since then.
        """
        graphql_files = []
        rest_files = []
        fetch_errors = []

        for repo_options in options:
            data = dict(repo_options)
            repo_name = cast(str, data["repo_name"])
            files = cast(List[FileSearchOptions], data["files"])
            changed_since = cast(Optional[RepositoryChange], data.get("changed_since"))

            logger.debug(
                f"Processing repository {repo_name} with {len(files)} file patterns"
            )

            try:
                gql, rest = await self.collect_matched_files(
                    repo_name, files, changed_since
                )
                graphql_files.extend(gql)
                rest_files.extend(rest)
            except GitHubTreeFetchError as e:
                logger.warning(f"Skipping {repo_name}: {e}")
                fetch_errors.append(e)
                continue

        logger.info(f"Processing {len(graphql_files)} GraphQL files")
        async for result in self.process_graphql_files(graphql_files):
            if result:
                yield result

        logger.info(f"Processing {len(rest_files)} REST API files")
        async for result in self.process_rest_api_files(rest_files):
            if result:
                yield result

        if fetch_errors:
            raise OceanAbortException(
                f"File fetch failed with {len(fetch_errors)} error(s): "
                f"Kind will be marked as synced with issues, entities preserved."
            ) from fetch_errors[0]

    async def collect_matched_files(
        self,
        repo_name: str,
        file_patterns: List[FileSearchOptions],
        changed_since: Optional[RepositoryChange] = None,
    ) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """Resolve file patterns to fetch lists, partitioned by GraphQL vs REST."""
        graphql_files = []
        rest_files = []

        for spec in file_patterns:
            pattern = spec["path"]
            skip_parsing = spec["skip_parsing"]
            organization = spec["organization"]

            repo_obj = await get_repository_metadata(
                self.client, organization, repo_name
            )
            if not repo_obj:
                logger.warning(
                    f"Repository {repo_name} not found in {organization}, skipping pattern '{pattern}'"
                )
                continue

            branch = spec.get("branch") or repo_obj["default_branch"]

            logger.debug(
                f"Processing pattern '{pattern}' on branch '{branch}' for {repo_name} from {organization}"
            )

            matched = await self._match_files(
                organization, repo_name, branch, pattern, changed_since
            )

            logger.info(
                f"Matched {len(matched)} files in {repo_name} with pattern '{pattern}' from {organization}"
            )

            for match in matched:
                path = match["path"]
                fetch_method = match["fetch_method"]

                file_info = {
                    "organization": organization,
                    "repo_name": repo_name,
                    "file_path": path,
                    "skip_parsing": skip_parsing,
                    "branch": branch,
                    "sha": match.get("sha"),
                }

                logger.debug(
                    f"File {path} will be fetched via {fetch_method} from {organization}"
                )

                if fetch_method == GithubClientType.GRAPHQL:
                    graphql_files.append(file_info)
                else:
                    rest_files.append(file_info)

        return graphql_files, rest_files

    async def _match_files(
        self,
        organization: str,
        repo_name: str,
        branch: str,
        pattern: str,
        changed_since: Optional[RepositoryChange] = None,
    ) -> List[Dict[str, Any]]:
        """Tree entries matching ``pattern``, limited to paths changed since ``changed_since``.

        Changed paths unknown (no ``changed_since``, or a compare that can't be
        trusted) means every matching file in the tree. When no changed path
        matches the pattern, the tree isn't fetched at all.
        """
        changed_paths = (
            await self.get_changed_paths_since(
                organization, repo_name, branch, changed_since
            )
            if changed_since is not None
            else None
        )
        if changed_paths is not None and not any(
            match_file_path_against_glob_pattern(path, pattern)
            for path in changed_paths
        ):
            return []

        # The tree gives each file's fetch_method and sha.
        tree, _ = await self.get_tree_recursive(organization, repo_name, branch)
        matched = filter_github_tree_entries_by_pattern(tree, pattern)
        if changed_paths is None:
            return matched
        return [m for m in matched if m["path"] in changed_paths]

    async def process_rest_api_files(
        self, files: List[Dict[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        batch_files = []
        for file_entry in files:
            organization = file_entry["organization"]
            repo_name = file_entry["repo_name"]
            file_path = file_entry["file_path"]
            skip_parsing = file_entry["skip_parsing"]
            branch = file_entry["branch"]

            file_data = await self.get_resource(
                FileContentOptions(
                    organization=organization,
                    repo_name=repo_name,
                    file_path=file_path,
                    branch=branch,
                )
            )

            if not file_data:
                logger.warning(f"File {file_path} not found from {organization}")
                continue

            decoded_content = file_data.pop("content", None)
            if decoded_content is None:
                logger.warning(f"File {file_path} has no content from {organization}")
                continue

            repository = await get_repository_metadata(
                self.client, organization, repo_name
            )
            if not repository:
                logger.warning(
                    f"Repository {repo_name} not found in {organization}, skipping file {file_path}"
                )
                continue

            file_obj = await self.file_processor.process_file(
                organization=organization,
                content=decoded_content,
                repository=repository,
                file_path=file_path,
                skip_parsing=skip_parsing,
                branch=branch,
                metadata=file_data,
            )

            batch_files.append(dict(file_obj))
            logger.debug(
                f"Successfully processed REST file: {file_path} from {organization}"
            )

        yield batch_files

    async def process_graphql_files(
        self, files: List[Dict[str, Any]]
    ) -> ASYNC_GENERATOR_RESYNC_TYPE:
        async for batch_result in self.process_files_in_batches(files):
            organization = batch_result["organization"]
            repo_name = batch_result["repo"]
            branch = batch_result["branch"]
            retrieved_files = batch_result["file_data"]["repository"]
            repository_metadata = await get_repository_metadata(
                self.client, organization, repo_name
            )
            if not repository_metadata:
                logger.warning(
                    f"Repository {repo_name} not found in {organization}, skipping GraphQL batch"
                )
                continue

            logger.debug(
                f"Retrieved {len(retrieved_files)} files from GraphQL batch from {organization}"
            )

            file_paths, file_metadata, file_shas = extract_file_paths_and_metadata(
                batch_result["batch_files"]
            )

            batch_files = await self._process_retrieved_graphql_files(
                organization,
                retrieved_files,
                file_paths,
                file_metadata,
                file_shas,
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

        grouped: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)
        for entry in matched_file_entries:
            key = (entry["organization"], entry["repo_name"], entry["branch"])
            grouped[key].append(entry)

        for (organization, repo_name, branch), entries in grouped.items():
            client = await create_github_client_for_org(
                organization, GithubClientType.GRAPHQL
            )
            for i in range(0, len(entries), batch_size):
                batch_files = entries[i : i + batch_size]
                logger.debug(
                    f"Processing batch of {len(batch_files)} files for {repo_name}@{branch}"
                )

                batch_file_paths = [entry["file_path"] for entry in batch_files]

                query_payload = build_batch_file_query(
                    repo_name, organization, branch, batch_file_paths
                )

                response = await client.send_api_request(
                    client.base_url, method="POST", json_data=query_payload
                )
                response_data = response.get("data")
                if not response or not response_data:
                    logger.warning(
                        f"No data returned for file batch in {repo_name}@{branch} from {organization}"
                    )
                    continue

                logger.info(
                    f"Fetched {len(batch_files)} files from {repo_name}:{branch} from {organization}"
                )

                yield {
                    "organization": organization,
                    "repo": repo_name,
                    "branch": branch,
                    "file_data": response_data,
                    "batch_files": batch_files,
                }

    async def _process_retrieved_graphql_files(
        self,
        organization: str,
        retrieved_files: Dict[str, Any],
        file_paths: List[str],
        file_metadata: Dict[str, bool],
        file_shas: Dict[str, Optional[str]],
        repository_metadata: Dict[str, Any],
        repo_name: str,
        branch: str,
    ) -> List[Dict[str, Any]]:
        batch_files = []

        for field_name, file_data in retrieved_files.items():
            file_index = extract_file_index(field_name)

            if file_index is None or file_index >= len(file_paths):
                logger.warning(
                    f"Unexpected field name format: '{field_name}' in {repo_name}@{branch} from {organization}"
                )
                continue

            file_path = file_paths[file_index]

            if file_data is None:
                logger.warning(f"File data for {file_path} is null from {organization}")
                continue

            content = file_data["text"]
            size = file_data.get("byteSize", 0)
            skip_parsing = file_metadata.get(file_path, False)

            if content is None:
                logger.warning(f"File {file_path} has no content from {organization}")
                continue

            file_obj = await self.file_processor.process_file(
                organization=organization,
                content=content,
                repository=repository_metadata,
                file_path=file_path,
                skip_parsing=skip_parsing,
                branch=branch,
                metadata=get_graphql_file_metadata(
                    self.client.base_url,
                    organization,
                    repo_name,
                    branch,
                    file_path,
                    size,
                    sha=file_shas.get(file_path),
                ),
            )

            batch_files.append(dict(file_obj))

        return batch_files

    @cache_coroutine_result()
    async def get_changed_paths_since(
        self,
        organization: str,
        repo_name: str,
        branch: str,
        changed_since: RepositoryChange,
    ) -> Optional[set[str]]:
        """Paths of files added or modified on ``branch`` since ``changed_since``.

        Cached per (repo, branch, field, since): the field is part of the key, so an
        ``updated_at`` change and a ``pushed_at`` change never share a result.

        Returns None when the diff cannot be trusted (no base commit, identical /
        rewritten history, truncated compare), so the caller falls back to a full
        tree scan.
        """
        base_sha = await self._resolve_compare_base_sha(
            organization, repo_name, branch, changed_since.since
        )
        if base_sha is None:
            return None

        files = await self._files_from_trusted_compare(
            organization, repo_name, base_sha, branch
        )
        if files is None:
            return None
        return {file["filename"] for file in files}

    async def _resolve_compare_base_sha(
        self, organization: str, repo_name: str, branch: str, until: datetime
    ) -> Optional[str]:
        """Newest commit on ``branch`` with committer date at or before ``until``.

        Filters by *committer date* among reachable commits, so this is not the
        historical branch tip at ``until``. No such commit means there is nothing
        safe to diff, so the caller scans the full tree.

        GitHub lists commits newest first, so only the first item of the first
        page is needed; the remaining pages are never requested.
        """
        resource = f"{self.client.base_url}/repos/{organization}/{repo_name}/commits"
        params = {
            "sha": branch,
            "until": until.astimezone(timezone.utc).isoformat(),
        }
        async for commits in self.client.send_paginated_request(
            resource, params=params, ignored_errors=self._IGNORED_ERRORS
        ):
            return commits[0]["sha"]

        logger.info(
            f"No base commit for {repo_name}@{branch} before {until.isoformat()}; using full tree"
        )
        return None

    async def _files_from_trusted_compare(
        self, organization: str, repo_name: str, base_sha: str, branch: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Files changed between ``base_sha`` and ``branch`` when the compare is complete.

        ``ahead`` and ``identical`` mean ``base_sha`` is an ancestor of the tip.
        GitHub caps the file list at 300 and does not mark it truncated, so a
        full list is treated as incomplete and the caller scans the full tree.
        """
        diff = await self.fetch_commit_diff(organization, repo_name, base_sha, branch)
        files = diff.get("files", [])
        if diff.get("status") not in COMPARE_BASE_IS_ANCESTOR_STATUSES:
            logger.info(
                f"Untrusted compare status '{diff.get('status')}' for {repo_name}@{branch}; using full tree"
            )
            return None
        if len(files) >= GITHUB_COMPARE_FILE_CAP:
            logger.info(
                f"Compare for {repo_name}@{branch} may be truncated ({len(files)} files); using full tree"
            )
            return None
        return files

    async def fetch_commit_diff(
        self, organization: str, repo_name: str, before_sha: str, after_sha: str
    ) -> Dict[str, Any]:
        """
        Fetch the commit comparison data from GitHub API.
        """

        resource = f"{self.client.base_url}/repos/{organization}/{repo_name}/compare/{before_sha}...{after_sha}"
        response = await self.client.send_api_request(resource)
        if not response:
            logger.warning(
                f"No commit diff found for {before_sha}...{after_sha} in {repo_name} from {organization}"
            )
            return {"files": []}

        logger.info(
            f"Found {len(response['files'])} files in commit diff from {organization}"
        )

        return response

    @cache_coroutine_result()
    async def get_tree_recursive(
        self, organization: str, repo: str, branch: str
    ) -> tuple[List[Dict[str, Any]], bool]:
        """Retrieve the recursive tree and whether GitHub truncated the response.

        Primary source for file kinds: 403 must raise GitHubTreeFetchError
        (synced-with-issues) so reconciliation does not treat the failure as an
        empty catalog. 404/409 are ignored so missing repos/branches skip
        without aborting the kind. Other HTTP errors abort the kind.
        """
        tree_url = f"{self.client.base_url}/repos/{organization}/{repo}/git/trees/{branch}?recursive=1"
        try:
            response = await self.client.send_api_request(
                tree_url,
                ignored_errors=self._IGNORED_ERRORS,
                ignore_default_errors=False,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 403:
                raise GitHubTreeFetchError(
                    f"Tree fetch failed for {organization}/{repo}@{branch}: "
                    f"GitHub API returned {e.response.status_code}. "
                    f"Entities will be preserved until next successful resync."
                ) from e
            logger.error(
                f"Tree fetch returned {e.response.status_code} for "
                f"{organization}/{repo}@{branch}, aborting resync"
            )
            raise

        if not response:
            logger.warning(
                f"Did not retrieve tree from {repo}@{branch} from {organization}"
            )
            return [], False

        truncated = bool(response.get("truncated"))
        if truncated:
            logger.warning(
                "Git tree was truncated by GitHub; file/plugin detection may be incomplete"
            )

        tree_items = response["tree"]
        logger.info(
            f"Retrieved tree for {repo}@{branch}: {len(tree_items)} items from {organization}"
        )
        return tree_items, truncated
