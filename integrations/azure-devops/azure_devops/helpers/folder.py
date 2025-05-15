from typing import Any, AsyncGenerator
from azure_devops.misc import FolderPattern
from azure_devops.client.azure_devops_client import AzureDevopsClient


async def process_folder_patterns(
    folder_patterns: list[FolderPattern], client: AzureDevopsClient
) -> AsyncGenerator[list[dict[str, Any]], None]:
    """Process folder patterns and yield matching folders.
    Args:
        folder_patterns: List of folder patterns to process
        client: Azure DevOps client instance
    """
    async for repositories in client.generate_repositories():
        for repo in repositories:
            for folder_pattern in folder_patterns:
                for repo_mapping in folder_pattern.repos:
                    if repo["name"] == repo_mapping.name:
                        async for found_folders in client.get_repository_folders(
                            repo["id"], [folder_pattern.path]
                        ):
                            enriched_folders = []
                            for folder in found_folders:
                                folder_dict = dict(folder)
                                folder_dict["__repository"] = repo
                                folder_dict["__branch"] = repo_mapping.branch
                                folder_dict["__pattern"] = folder_pattern.path
                                enriched_folders.append(folder_dict)
                            yield enriched_folders
