import fnmatch
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator, Optional, Tuple
from loguru import logger
from integration import BitbucketServerFilePattern
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from utils import initialize_client

async def get_repositories_for_pattern(
    client, file_pattern: BitbucketServerFilePattern
) -> List[Dict[str, Any]]:
    """Get repositories matching the given file pattern."""
    repos_to_process = []

    # Handle wildcard project key differently
    if file_pattern.project_key == "*":
        # Get all projects first
        async for project_batch in client.get_projects():
            for project in project_batch:
                project_key = project["key"]
                logger.info(f"Processing project: {project_key}")
                # For each project, get its repositories
                await collect_repos_for_project(
                    client, project_key, file_pattern.repos, repos_to_process
                )
    else:
        # Use the specific project key
        await collect_repos_for_project(
            client, file_pattern.project_key, file_pattern.repos, repos_to_process
        )

    return repos_to_process


async def collect_repos_for_project(
    client, project_key: str, repo_filter: List[str], repos_list: List[Dict[str, Any]]
) -> None:
    """Collect repositories for a specific project that match the filter."""
    async for repo_batch in client.get_repositories_for_project(project_key):
        for repo in repo_batch:
            if not repo_filter or repo["slug"] in repo_filter:
                repos_list.append(repo)


async def process_matching_file(
    client, project_key: str, repo_slug: str, file_path: str, repo: Dict[str, Any]
) -> Optional[Dict[str, Any]]:
    """Process a matching file and return its content and metadata."""
    try:
        # Get the file content
        file_content = await client.get_file_content(
            project_key, repo_slug, file_path
        )

        # Create file object with metadata
        file_obj = create_file_metadata(file_path, file_content)

        result = {
            "content": file_content,
            "repo": repo,
            "project": {"key": project_key},
            "file": file_obj,
            "path": file_path,
            "filename": Path(file_path).name
        }

        return result
    except Exception as e:
        logger.error(f"Failed to retrieve file content for {file_path} from {repo_slug}: {e}")
        return None


def create_file_metadata(file_path: str, file_content: str) -> Dict[str, Any]:
    """Create metadata for a file based on its path and content."""
    file_obj = {
        "path": file_path,
        "size": len(file_content),
        "type": "FILE",
        "contentType": "text/plain",  # Default content type
        "lastModified": None  # No last modified info available
    }

    # Set content type based on extension
    extension = Path(file_path).suffix.lstrip('.')
    if extension in ['py', 'js', 'ts', 'java', 'c', 'cpp', 'cs']:
        file_obj["contentType"] = "text/plain"
    elif extension in ['md', 'txt']:
        file_obj["contentType"] = "text/plain"
    elif extension in ['json']:
        file_obj["contentType"] = "application/json"
    elif extension in ['yml', 'yaml']:
        file_obj["contentType"] = "application/yaml"

    return file_obj


async def process_repository_files(
    client, repo: Dict[str, Any], file_pattern: BitbucketServerFilePattern
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Process files in a repository that match the given pattern."""
    repo_slug = repo["slug"]
    project_key = repo["project"]["key"]

    try:
        # Start with the root directory
        base_path = ""
        all_files = []

        # Recursively list files in the repository
        await list_files_recursively(client, project_key, repo_slug, base_path, all_files)

        # Filter and process matching files
        for file_info in all_files:
            file_path = file_info.get("path", "")

            # Check if the file matches our patterns
            if matches_file_pattern(file_path, file_pattern.path, file_pattern.filenames):
                result = await process_matching_file(
                    client, project_key, repo_slug, file_path, repo
                )
                if result:
                    yield [result]
    except Exception as e:
        logger.error(f"Failed to list files in repository {repo_slug}: {e}")


async def process_file_patterns(
    file_pattern: BitbucketServerFilePattern,
) -> AsyncGenerator[List[Dict[str, Any]], None]:
    """Process file patterns and retrieve matching files."""
    logger.info(
        f"Searching for files in project {file_pattern.project_key} with pattern: {file_pattern.path}"
    )

    if not file_pattern.project_key:
        logger.warning("No project key provided, skipping file search")
        return
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file search")
        return

    bitbucket_client = initialize_client()

    # Get repositories matching the pattern
    repos_to_process = await get_repositories_for_pattern(bitbucket_client, file_pattern)

    # Process each repository
    for repo in repos_to_process:
        async for result in process_repository_files(bitbucket_client, repo, file_pattern):
            yield result

async def list_files_recursively(client, project_key, repo_slug, path, result_list):
    """Recursively list all files in a repository."""
    try:
        # Handle empty or wildcard path
        path_to_use = "" if path == "*" else path

        # Get contents of the current directory
        async for contents in client.get_directory_contents(project_key, repo_slug, path_to_use):
            for item in contents:
                await process_directory_item(client, project_key, repo_slug, item, result_list)
    except Exception as e:
        logger.error(f"Error listing directory {path} in {repo_slug}: {e}")


async def process_directory_item(client, project_key, repo_slug, item, result_list):
    """Process a single item from directory contents."""
    # Handle different response formats
    if isinstance(item, dict) and "path" in item and "type" in item:
        # Dictionary format
        await process_typed_item(client, project_key, repo_slug, item, result_list)
    elif isinstance(item, str):
        # String format - assume it's a file path
        await process_string_item(client, project_key, repo_slug, item, result_list)


async def process_typed_item(client, project_key, repo_slug, item, result_list):
    """Process an item that has explicit type information."""
    item_path = item["path"]
    item_type = item["type"]

    if item_type == "FILE":
        # Add file to the result list
        result_list.append(item)
    elif item_type == "DIRECTORY":
        # Recursively process subdirectory
        await list_files_recursively(client, project_key, repo_slug, item_path, result_list)


async def process_string_item(client, project_key, repo_slug, item_path, result_list):
    """Process an item that is represented as a string path."""
    # Create a synthetic file object
    file_obj = {
        "path": item_path,
        "type": "FILE" if not item_path.endswith("/") else "DIRECTORY"
    }

    if file_obj["type"] == "FILE":
        result_list.append(file_obj)
    else:
        # Remove trailing slash for directory path
        dir_path = item_path.rstrip("/")
        await list_files_recursively(client, project_key, repo_slug, dir_path, result_list)

def matches_file_pattern(file_path, pattern_path, filenames):
    """Check if a file path matches the given pattern and filenames."""
    # If pattern_path is empty or *, match any directory
    if not pattern_path or pattern_path == "*":
        return matches_filename_only(file_path, filenames)

    # If pattern includes directory structure
    return matches_path_and_filename(file_path, pattern_path, filenames)


def matches_filename_only(file_path, filenames):
    """Check if the filename matches any of the filename patterns."""
    file_name = Path(file_path).name
    return any(fnmatch.fnmatch(file_name, filename) for filename in filenames)


def matches_path_and_filename(file_path, pattern_path, filenames):
    """Check if both the path and filename match the patterns."""
    # Convert simple wildcards to recursive wildcards for path matching
    path_pattern = pattern_path.replace("*", "**")

    # Check if the file path matches the directory pattern
    if fnmatch.fnmatch(file_path, f"{path_pattern}/*"):
        # If directory matches, check filename
        return matches_filename_only(file_path, filenames)

    return False
