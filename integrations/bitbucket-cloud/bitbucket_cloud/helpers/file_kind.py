import fnmatch
import json
import re
from typing import Dict, List, Any, AsyncGenerator, Set
from loguru import logger
import yaml
from integration import BitbucketFilePattern, BitbucketFileSelector
from bitbucket_cloud.client import BitbucketClient
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")


def calculate_required_depth(pattern: str, depth: int) -> int:
    """
    Calculate the required depth for recursive search based on the pattern.
    """
    return depth if "**/" in pattern else min(pattern.count("/") + 1, depth)


def calculate_base_path(selector: BitbucketFileSelector) -> str:
    if not selector.files:
        return "/"

    file_path = selector.files.path
    logger.debug(f"File path: {file_path}")
    if file_path.startswith("**/"):
        return "/"

    # Match the base directory up to the first wildcard or pattern character
    base_match = re.match(r"^([^*[?]*/)?", file_path)
    logger.debug(f"Base match: {base_match}")
    base_dir = base_match[0] if base_match else "/"

    # Ensure the base directory ends with a slash
    if not base_dir.endswith("/"):
        base_dir = f"{base_dir}/"

    return base_dir


def _match_files_with_pattern(
    files: List[Dict[str, Any]], pattern: str
) -> List[Dict[str, Any]]:
    """
    Match files against a glob pattern.
    """
    if not pattern:
        return files

    paths = [file.get("path", "") for file in files]
    matched_paths: Set[str] = set()

    if pattern.startswith("**/"):
        root_pattern = pattern[3:]  # Match files in root directory
        matched_paths.update(
            path
            for path in paths
            if fnmatch.fnmatch(path, root_pattern.replace("**", "*"))
        )

    matched_paths.update(
        path for path in paths if fnmatch.fnmatch(path, pattern.replace("**", "*"))
    )

    return [file for file in files if file.get("path", "") in matched_paths]


async def process_repository(
    repo_slug: str,
    pattern: str,
    client: BitbucketClient,
    base_path: str,
    skip_parsing: bool,
    batch_size: int,
    depth: int = 2,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Process a single repository to find matching files.
    """
    try:
        max_depth = calculate_required_depth(pattern, depth)
        query_params = {
            "pagelen": batch_size,
            "max_depth": max_depth,
            "q": 'type="commit_file"',
        }

        repo = await client.get_repository(repo_slug)
        branch = repo.get("mainbranch", {}).get("name", "master")

        async for files_batch in client.get_directory_contents(
            repo_slug, branch=branch, path=base_path, params=query_params
        ):
            matched_files = _match_files_with_pattern(files_batch, pattern)
            logger.debug(f"Matched files: {matched_files}")
            tasks = [
                retrieve_matched_file_contents([file], client, repo_slug, branch, repo)
                for file in matched_files
            ]

            async for file_results in stream_async_iterators_tasks(*tasks):
                if skip_parsing:
                    yield file_results
                else:
                    logger.debug(f"Result: {file_results}")
                    parsed_results = parse_file(file_results)
                    logger.debug(f"Parsed results: {parsed_results}")
                    yield parsed_results

        logger.info(
            f"Finished scanning {repo_slug}, found {len(matched_files)} matching file paths"
        )
    except Exception as e:
        logger.error(f"Error scanning files in repository {repo_slug}: {str(e)}")
        return


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
    client: BitbucketClient,
    base_path: str = "/",
    format: str = "meta",
    batch_size: int = 100,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Process file patterns and retrieve matching files efficiently using concurrent processing.
    """
    pattern = file_pattern.path
    repos = file_pattern.repos
    skip_parsing = file_pattern.skip_parsing
    depth = file_pattern.depth

    if not repos:
        logger.warning("No repositories specified - skipping file processing")
        return

    logger.info(f"Searching for pattern '{pattern}' in {len(repos)} repositories")

    tasks = [
        process_repository(
            repo_slug=repo_slug,
            pattern=pattern,
            client=client,
            base_path=base_path,
            skip_parsing=skip_parsing,
            batch_size=batch_size,
            depth=depth,
        )
        for repo_slug in repos
    ]
    async for results in stream_async_iterators_tasks(*tasks):
        yield results


async def retrieve_matched_file_contents(
    matched_files: List[Dict[str, Any]],
    client: BitbucketClient,
    repo_slug: str,
    branch: str,
    repo: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """
    Retrieve the contents of matched files.
    """
    for matched_file in matched_files:
        file_path = matched_file.get("path", "")
        file_content = await client.get_repository_files(repo_slug, branch, file_path)
        yield {
            "content": file_content,
            "repo": repo,
            "branch": branch,
            "metadata": matched_file,
        }


def parse_file(file: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Parse a file based on its extension.
    """
    file_path = file.get("metadata", {}).get("path", "")
    file_content = file.get("content", "")
    if file_path.endswith(JSON_FILE_SUFFIX):
        loaded_file = json.loads(file_content)
        file["content"] = loaded_file
    elif file_path.endswith(YAML_FILE_SUFFIX):
        loaded_file = yaml.safe_load(file_content)
        file["content"] = loaded_file
    return [file]
