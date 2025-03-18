import fnmatch
import json
import os
from typing import Dict, List, Any, Set, AsyncGenerator
from loguru import logger
import yaml
from integration import BitbucketFilePattern, BitbucketFileSelector
from client import BitbucketClient

JSON_FILE_SUFFIX = ".json"
YAML_FILE_SUFFIX = [".yaml", ".yml"]


def calculate_base_path(selector: BitbucketFileSelector) -> str:
    if not selector.files:
        return "/"

    file_path = selector.files.path
    if "**/" in file_path:
        base_dir = file_path.split("**/")[0]
    elif "*" in file_path and "/" in file_path:
        base_dir = file_path.split("*")[0]
    elif "[" in file_path and "]" in file_path and "/" in file_path:
        base_dir = file_path.split("[")[0]
    elif "/" in file_path:
        if file_path.endswith("/"):
            return file_path
        last_slash = file_path.rfind("/")
        return file_path[: last_slash + 1] if last_slash != -1 else "/"
    else:
        return "/"

    if base_dir and not base_dir.endswith("/"):
        last_slash = base_dir.rfind("/")
        base_dir = base_dir[: last_slash + 1] if last_slash != -1 else f"{base_dir}/"
    return base_dir or "/"


async def _match_files_with_pattern(
    files: List[Dict[str, Any]], pattern: str
) -> List[Dict[str, Any]]:
    """
    Match files against a glob pattern.
    """
    if not pattern:
        return files

    matched_files = []

    for file in files:
        file_path = file.get("path", "")

        # Handle patterns with **/ in the middle (e.g., "path/**/file.yaml")
        if "**/" in pattern:
            # Split the pattern into prefix and suffix around the first **/
            parts = pattern.split("**/", 1)
            prefix = parts[0]
            suffix = parts[1] if len(parts) > 1 else ""

            if prefix and suffix:
                if file_path.startswith(prefix) and file_path.endswith(suffix):
                    matched_files.append(file)
                    continue
            elif prefix:
                if file_path.startswith(prefix):
                    matched_files.append(file)
                    continue
            elif suffix:
                if file_path.endswith(suffix) or fnmatch.fnmatch(
                    os.path.basename(file_path), suffix
                ):
                    matched_files.append(file)
                    continue
        elif fnmatch.fnmatch(file_path, pattern):
            matched_files.append(file)
            continue
        elif pattern.endswith("/") and file_path.startswith(pattern):
            matched_files.append(file)
            continue

    return matched_files


async def process_file_patterns(
    file_pattern: BitbucketFilePattern,
    client: BitbucketClient,
    base_path: str = "/",
    format: str = "meta",
    batch_size: int = 100,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Process file patterns and retrieve matching files efficiently.
    """
    pattern = file_pattern.path
    repos = file_pattern.repos
    skip_parsing = file_pattern.skip_parsing

    if not repos:
        logger.warning("No repositories specified - skipping file processing")
        return

    logger.info(f"Searching for pattern '{pattern}' in {len(repos)} repositories")

    processed_repos: Set[str] = set()

    for repo_slug in repos:
        if repo_slug in processed_repos:
            continue
        processed_repos.add(repo_slug)
        try:
            query_params = {
                "pagelen": batch_size,
                "max_depth": 2,
                "q": 'type="commit_file"',
            }

            repo = await client.get_repository(repo_slug)
            branch = repo.get("mainbranch", {}).get("name", "master")
            async for files_batch in client.get_directory_contents(
                repo_slug, branch=branch, path=base_path, params=query_params
            ):
                matched_files = await _match_files_with_pattern(files_batch, pattern)
                async for matched_file in retrieve_matched_file_contents(
                    matched_files, client, repo_slug, branch, repo
                ):
                    if skip_parsing:
                        yield matched_file
                    else:
                        yield parse_file(matched_file)
            logger.info(
                f"Finished scanning {repo_slug}, found {len(matched_files)} matching file paths"
            )
        except Exception as e:
            logger.error(f"Error scanning files in repository {repo_slug}: {str(e)}")
            continue


async def retrieve_matched_file_contents(
    matched_files: List[Dict[str, Any]],
    client: BitbucketClient,
    repo_slug: str,
    branch: str,
    repo: Dict[str, Any],
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """
    Retrieve the contents of matched files.
    """
    for matched_file in matched_files:
        file_path = matched_file.get("path", "")
        file_content = await client.get_repository_files(repo_slug, branch, file_path)
        yield [
            {
                "content": file_content,
                "repo": repo,
                "branch": branch,
                "metadata": matched_file,
            }
        ]


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
