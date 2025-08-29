import fnmatch
from pathlib import Path
from typing import Dict, List, Any, AsyncGenerator, Optional
from loguru import logger
from integration import BitbucketServerFilePattern
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from initialize_client import init_client

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
    if not file_pattern.path:
        logger.info("Path is required, skipping file search")
        return
    if not file_pattern.filenames:
        logger.info("No filenames provided, skipping file search")
        return

    bitbucket_client = init_client()

    # Get repositories in the project
    repos_to_process = []
    async for repo_batch in bitbucket_client.get_repositories_for_project(file_pattern.project_key):
        for repo in repo_batch:
            if not file_pattern.repos or repo["slug"] in file_pattern.repos:
                repos_to_process.append(repo)

    for repo in repos_to_process:
        repo_slug = repo["slug"]
        for filename in file_pattern.filenames:
            file_path = f"{file_pattern.path}/{filename}"
            try:
                file_content = await bitbucket_client.get_file_content(
                    file_pattern.project_key, repo_slug, file_path
                )

                result = {
                    "content": file_content,
                    "repo": repo,
                    "project": {"key": file_pattern.project_key},
                    "path": file_path,
                    "filename": filename
                }

                yield [result]
            except Exception as e:
                logger.error(f"Failed to retrieve file {file_path} from {repo_slug}: {e}")
