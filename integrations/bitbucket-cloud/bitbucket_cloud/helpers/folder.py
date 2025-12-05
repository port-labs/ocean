from collections import defaultdict
from typing import Any, AsyncGenerator, Dict, List, Set, Tuple, TYPE_CHECKING

from loguru import logger
from wcmatch import glob
from integration import FolderPattern


if TYPE_CHECKING:
    from bitbucket_cloud.client import BitbucketClient


def extract_repo_names_from_patterns(
    folder_patterns: List[FolderPattern],
) -> Set[str] | None:
    """Extract repository names from folder patterns."""
    if not folder_patterns:
        logger.info("No folder patterns found in config, skipping folder sync")
        return set()

    repo_names = {repo.name for pattern in folder_patterns for repo in pattern.repos}
    if not repo_names:
        logger.info(
            "No repository names found in patterns, syncing folders from all repositories in workspace"
        )
        return None

    return repo_names


def extract_global_patterns(folder_patterns: List[FolderPattern]) -> List[str]:
    return [
        pattern.path
        for pattern in folder_patterns
        if not pattern.repos and pattern.path
    ]


def create_pattern_mapping(
    folder_patterns: List[FolderPattern],
) -> Tuple[Dict[str, Dict[str, List[str]]] | None, List[str]]:
    """Create a mapping of repository names to branch names to folder patterns."""
    pattern_by_repo_branch: Dict[str, Dict[str, List[str]]] = defaultdict(
        lambda: defaultdict(list)
    )

    has_repos = False
    for pattern in folder_patterns:
        p = pattern.path
        if not pattern.repos:
            continue
        has_repos = True
        for repo in pattern.repos:
            pattern_by_repo_branch[repo.name][repo.branch].append(p)

    repo_mapping = (
        None
        if not has_repos
        else {repo: dict(branches) for repo, branches in pattern_by_repo_branch.items()}
    )
    global_patterns = extract_global_patterns(folder_patterns)

    return repo_mapping, global_patterns


def find_matching_folders(
    contents: List[Dict[str, Any]],
    patterns: List[str],
    repo: Dict[str, Any],
    branch: str,
) -> List[Dict[str, Any]]:
    """Find folders that match the given patterns."""
    matching_folders = []
    for pattern_str in patterns:
        matching = [
            {"folder": folder, "repo": repo, "pattern": pattern_str, "branch": branch}
            for folder in contents
            if folder["type"] == "commit_directory"
            and glob.globmatch(
                folder["path"], pattern_str, flags=glob.GLOBSTAR | glob.DOTGLOB
            )
        ]
        matching_folders.extend(matching)
    return matching_folders


def get_parts_before_wildcard(path: str) -> List[str]:
    parts = path.split("/")
    result = []
    for part in parts:
        if any(c in part for c in "*?[]"):
            break
        result.append(part)
    return result


def find_common_base_path_and_max_depth(paths: List[str]) -> Tuple[str, int]:
    """
    Find the common base path and max depth for a list of path patterns.
    """
    if not paths:
        return "", 1

    all_path_parts = [get_parts_before_wildcard(path) for path in paths]

    common_parts = []
    if all_path_parts and all_path_parts[0]:
        for i in range(min(len(path_parts) for path_parts in all_path_parts)):
            current_part = all_path_parts[0][i]
            if all(path_parts[i] == current_part for path_parts in all_path_parts):
                common_parts.append(current_part)
            else:
                break

    base_path = "/".join(common_parts)

    # Calculate relative paths and required depth
    relative_paths = [
        p[len(base_path) :].lstrip("/") if base_path and p.startswith(base_path) else p
        for p in paths
    ]

    max_pattern_depth = max(
        (path.count("/") + 1 for path in relative_paths),
        default=1,
    )
    return base_path, max_pattern_depth


async def process_folder_patterns(
    folder_patterns: list[FolderPattern],
    client: "BitbucketClient",
    params: dict[str, Any] = {},
) -> AsyncGenerator[list[dict[str, Any]], None]:
    repo_names = extract_repo_names_from_patterns(folder_patterns)
    if repo_names is not None and not repo_names:
        return

    if "role" in params:
        params["role"] = params["role"]

    pattern_by_repo, global_patterns = create_pattern_mapping(folder_patterns)

    # If repos are specified, process those repos with their specific patterns + global patterns
    if repo_names is not None:
        name_filter = f"name IN ({','.join(f'"{name}"' for name in repo_names)})"
        q_param = f"{name_filter} AND ({params['q']})" if "q" in params else name_filter
        params["q"] = q_param
        async for repos_batch in client.get_repositories(params=params):
            for repo in repos_batch:
                async for matching_folders in process_repo_folders(
                    repo, pattern_by_repo, global_patterns, client
                ):
                    yield matching_folders

    # If there are global patterns, apply them to all repos (not just the ones specified above)
    if global_patterns:
        # If we already processed specific repos, we need to process the remaining repos with global patterns
        if repo_names is not None:
            async for repos_batch in client.get_repositories(params=params):
                for repo in repos_batch:
                    repo_name = repo["name"].replace(" ", "-")
                    # Skip repos that were already processed with specific patterns
                    if repo_name in repo_names:
                        continue
                    async for matching_folders in process_repo_folders_global(
                        repo, global_patterns, client
                    ):
                        yield matching_folders
        else:
            # No specific repos, just process all repos with global patterns
            async for repos_batch in client.get_repositories():
                for repo in repos_batch:
                    async for matching_folders in process_repo_folders_global(
                        repo, global_patterns, client
                    ):
                        yield matching_folders


async def process_repo_folders(
    repo: dict[str, Any],
    pattern_by_repo: dict[str, dict[str, list[str]]] | None,
    global_patterns: list[str],
    client: "BitbucketClient",
) -> AsyncGenerator[list[dict[str, Any]], None]:
    repo_name = repo["name"].replace(" ", "-")

    # Collect all patterns for this repo: repo-specific + global patterns
    all_patterns_by_branch: dict[str, list[str]] = defaultdict(list)

    # Add repo-specific patterns
    if pattern_by_repo and repo_name in pattern_by_repo:
        for branch, paths in pattern_by_repo[repo_name].items():
            all_patterns_by_branch[branch].extend(paths)

    # Add global patterns to the default branch
    if global_patterns:
        default_branch = "default"
        all_patterns_by_branch[default_branch].extend(global_patterns)

    if not all_patterns_by_branch:
        return

    for branch, paths in all_patterns_by_branch.items():
        repo_slug = repo.get("slug", repo_name.lower())
        effective_branch = branch if branch != "default" else repo["mainbranch"]["name"]
        base_path, max_pattern_depth = find_common_base_path_and_max_depth(paths)
        logger.debug(
            f"Fetching {repo_name}/{effective_branch} from '{base_path}' with depth {max_pattern_depth}"
        )

        async for contents in client.get_directory_contents(
            repo_slug, effective_branch, base_path, max_depth=max_pattern_depth
        ):
            if matching_folders := find_matching_folders(
                contents, paths, repo, effective_branch
            ):
                yield matching_folders


async def process_repo_folders_global(
    repo: dict[str, Any],
    global_patterns: list[str],
    client: "BitbucketClient",
) -> AsyncGenerator[list[dict[str, Any]], None]:
    if not global_patterns:
        return

    repo_name = repo["name"].replace(" ", "-")
    repo_slug = repo.get("slug", repo_name.lower())
    effective_branch = repo["mainbranch"]["name"]

    base_path, max_pattern_depth = find_common_base_path_and_max_depth(global_patterns)
    logger.debug(
        f"Fetching {repo_name}/{effective_branch} from '{base_path}' with depth {max_pattern_depth}"
    )

    async for contents in client.get_directory_contents(
        repo_slug, effective_branch, base_path, max_depth=max_pattern_depth
    ):
        if matching_folders := find_matching_folders(
            contents, global_patterns, repo, effective_branch
        ):
            yield matching_folders
