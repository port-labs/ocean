import fnmatch
import json
from typing import Dict, List, Any, AsyncGenerator
from loguru import logger
import yaml
from integration import BitbucketFilePattern
from bitbucket_cloud.client import BitbucketClient
from port_ocean.utils.async_iterators import stream_async_iterators_tasks


JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = (".yaml", ".yml")


def build_search_terms(
    filename: str, repos: List[str] | None, path: str | None, extension: str
) -> str:
    """Build search terms for Bitbucket's search API."""
    search_terms = [f'"{filename}"']
    if repos:
        repo_filters = " ".join(f"repo:{repo}" for repo in repos)
        search_terms.append(f"{repo_filters}")

    if path:
        search_terms.append(f"path:{path}")

    if extension:
        search_terms.append(f"ext:{extension}")

    return " ".join(search_terms)


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
    client: BitbucketClient,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Process file patterns and retrieve matching files using Bitbucket's search API."""
    logger.info(
        f"Searching for files in {len(file_pattern.repos) if file_pattern.repos else 'all'} repositories with pattern: {file_pattern.path}"
    )

    for filename in file_pattern.filenames:
        search_query = build_search_terms(
            filename=filename,
            repos=file_pattern.repos,
            path=file_pattern.path,
            extension=filename.split(".")[-1],
        )
        logger.debug(f"Constructed search query: {search_query}")

        async for search_results in client.search_files(search_query):
            tasks = []
            for result in search_results:
                if len(result["path_matches"]) >= 1:
                    file_info = result["file"]
                    repo_info = file_info["commit"]["repository"]
                    repo_slug = repo_info["name"]
                    file_path = file_info["path"]
                    branch = repo_info["mainbranch"]["name"]

                    if not validate_file_match(file_path, filename, file_pattern.path):
                        logger.debug(
                            f"Skipping file {file_path} as it doesn't match expected patterns"
                        )
                        continue

                    tasks.append(
                        retrieve_matched_file_contents(
                            matched_files=[file_info],
                            client=client,
                            repo_slug=repo_slug,
                            branch=branch,
                            repo=repo_info,
                        )
                    )

            async for file_results in stream_async_iterators_tasks(*tasks):
                if not file_pattern.skip_parsing:
                    file_results = parse_file(file_results)
                yield [file_results]


async def retrieve_matched_file_contents(
    matched_files: List[Dict[str, Any]],
    client: BitbucketClient,
    repo_slug: str,
    branch: str,
    repo: Dict[str, Any],
) -> AsyncGenerator[Dict[str, Any], None]:
    """Retrieve the contents of matched files."""
    logger.info(f"Retrieving contents for {len(matched_files)} files")
    for matched_file in matched_files:
        file_path = matched_file.get("path", "")
        file_content = await client.get_repository_files(repo_slug, branch, file_path)
        yield {
            "content": file_content,
            "repo": repo,
            "branch": branch,
            "metadata": matched_file,
        }


def parse_file(file: Dict[str, Any]) -> Dict[str, Any]:
    """Parse a file based on its extension."""
    file_path = file.get("metadata", {}).get("path", "")
    file_content = file.get("content", "")
    if file_path.endswith(JSON_FILE_SUFFIX):
        loaded_file = json.loads(file_content)
        file["content"] = loaded_file
    elif file_path.endswith(YAML_FILE_SUFFIX):
        loaded_file = yaml.safe_load(file_content)
        file["content"] = loaded_file
    return file


def validate_file_match(file_path: str, filename: str, expected_path: str) -> bool:
    """Validate if the file path and filename match the expected patterns."""
    if not file_path.endswith(filename):
        return False

    if not expected_path or expected_path == "/":
        return True

    dir_path = file_path[: -len(filename)]
    dir_path = dir_path.rstrip("/")
    expected_path = expected_path.rstrip("/")
    return fnmatch.fnmatch(dir_path, expected_path)
