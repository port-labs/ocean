import fnmatch
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator, Optional
from loguru import logger
from integration import BitbucketServerFilePattern
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from utils import initialize_client

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

    # Get repositories in the project
    repos_to_process = []

    # Handle wildcard project key differently
    if file_pattern.project_key == "*":
        # Get all projects first
        async for project_batch in bitbucket_client.get_projects():
            for project in project_batch:
                project_key = project["key"]
                logger.info(f"Processing project: {project_key}")
                # For each project, get its repositories
                async for repo_batch in bitbucket_client.get_repositories_for_project(project_key):
                    for repo in repo_batch:
                        if not file_pattern.repos or repo["slug"] in file_pattern.repos:
                            repos_to_process.append(repo)
    else:
        # Use the specific project key
        async for repo_batch in bitbucket_client.get_repositories_for_project(file_pattern.project_key):
            for repo in repo_batch:
                if not file_pattern.repos or repo["slug"] in file_pattern.repos:
                    repos_to_process.append(repo)

    for repo in repos_to_process:
        repo_slug = repo["slug"]
        # Get the actual project key from the repository object
        project_key = repo["project"]["key"]

        # First, get a list of all files in the repository
        try:
            # Start with the root directory
            base_path = ""
            all_files = []

            # Recursively list files in the repository - use actual project key
            await list_files_recursively(bitbucket_client, project_key, repo_slug, base_path, all_files)

            # Now filter files based on the pattern and filenames
            for file_info in all_files:
                file_path = file_info.get("path", "")

                # Check if the file matches our patterns
                if matches_file_pattern(file_path, file_pattern.path, file_pattern.filenames):
                    try:
                        # Get the file content - use actual project key
                        file_content = await bitbucket_client.get_file_content(
                            project_key, repo_slug, file_path
                        )

                        # Create a complete file object with all required properties
                        file_obj = {
                            "path": file_path,
                            "size": len(file_content),  # Use content length as size
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

                        result = {
                            "content": file_content,
                            "repo": repo,
                            "project": {"key": project_key},  # Use actual project key
                            "file": file_obj,  # Add complete file object
                            "path": file_path,
                            "filename": Path(file_path).name
                        }

                        yield [result]
                    except Exception as e:
                        logger.error(f"Failed to retrieve file content for {file_path} from {repo_slug}: {e}")
        except Exception as e:
            logger.error(f"Failed to list files in repository {repo_slug}: {e}")

async def list_files_recursively(client, project_key, repo_slug, path, result_list):
    """Recursively list all files in a repository."""
    try:
        # Handle empty or wildcard path
        path_to_use = "" if path == "*" else path

        # Get contents of the current directory
        async for contents in client.get_directory_contents(project_key, repo_slug, path_to_use):
            for item in contents:
                # Handle different response formats
                if isinstance(item, dict) and "path" in item and "type" in item:
                    # Dictionary format
                    item_path = item["path"]
                    item_type = item["type"]

                    if item_type == "FILE":
                        # Add file to the result list
                        result_list.append(item)
                    elif item_type == "DIRECTORY":
                        # Recursively process subdirectory
                        await list_files_recursively(client, project_key, repo_slug, item_path, result_list)
                elif isinstance(item, str):
                    # String format - assume it's a file path
                    # Create a synthetic file object
                    file_obj = {
                        "path": item,
                        "type": "FILE" if not item.endswith("/") else "DIRECTORY"
                    }

                    if file_obj["type"] == "FILE":
                        result_list.append(file_obj)
                    else:
                        # Remove trailing slash for directory path
                        dir_path = item.rstrip("/")
                        await list_files_recursively(client, project_key, repo_slug, dir_path, result_list)
    except Exception as e:
        logger.error(f"Error listing directory {path} in {repo_slug}: {e}")

def matches_file_pattern(file_path, pattern_path, filenames):
    """Check if a file path matches the given pattern and filenames."""
    # If pattern_path is empty or *, match any directory
    if not pattern_path or pattern_path == "*":
        # Just check filename patterns
        file_name = Path(file_path).name
        return any(fnmatch.fnmatch(file_name, filename) for filename in filenames)

    # If pattern includes directory structure
    path_pattern = pattern_path.replace("*", "**")

    # Check if the file path matches the directory pattern
    if fnmatch.fnmatch(file_path, f"{path_pattern}/*"):
        # If directory matches, check filename
        file_name = Path(file_path).name
        return any(fnmatch.fnmatch(file_name, filename) for filename in filenames)

    return False
