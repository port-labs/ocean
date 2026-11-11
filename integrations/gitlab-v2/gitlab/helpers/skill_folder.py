import asyncio
from pathlib import PurePosixPath
from typing import Any

from loguru import logger

from gitlab.clients.gitlab_client import GitLabClient
from gitlab.helpers.skill_plugin import SKILL_MD_FILENAME

TEXT_FILE_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".md",
        ".mdx",
        ".markdown",
        ".txt",
        ".rst",
        ".json",
        ".jsonl",
        ".yaml",
        ".yml",
        ".toml",
        ".ini",
        ".cfg",
        ".csv",
        ".tsv",
        ".xml",
        ".html",
        ".htm",
        ".css",
        ".sql",
        ".py",
        ".sh",
        ".bash",
        ".ps1",
        ".js",
        ".mjs",
        ".cjs",
        ".ts",
        ".tsx",
        ".jsx",
        ".rb",
        ".go",
        ".java",
        ".rs",
        ".tf",
    }
)
MAX_SKILL_BUNDLE_SIZE = 1024 * 1024
MAX_SKILL_FOLDER_DEPTH = 5
# Git tree mode for symlinks: their "content" is a target path that may point
# outside the skill folder, so they are never bundled.
SYMLINK_MODE = "120000"


def skill_dir_prefix(skill_md_path: str) -> str:
    """Path prefix shared by every file inside the skill folder ("" at repo root)."""
    skill_dir = str(PurePosixPath(skill_md_path).parent)
    return "" if skill_dir == "." else f"{skill_dir}/"


def select_skill_folder_files(
    tree: list[dict[str, Any]], skill_md_path: str
) -> list[dict[str, Any]]:
    """Pick the text files in a skill's folder from an already fetched git tree.

    Files that belong to a nested skill (a subfolder with its own SKILL.md)
    are left to that skill.
    """
    prefix = skill_dir_prefix(skill_md_path)
    candidates = [
        entry
        for entry in tree
        if entry.get("type") == "blob"
        and entry.get("mode") != SYMLINK_MODE
        and entry["path"].startswith(prefix)
        and entry["path"] != skill_md_path
    ]
    nested_skill_prefixes = tuple(
        skill_dir_prefix(entry["path"])
        for entry in candidates
        if PurePosixPath(entry["path"]).name.lower() == SKILL_MD_FILENAME.lower()
    )

    selected = []
    for entry in candidates:
        relative_path = entry["path"].removeprefix(prefix)
        if (
            relative_path.count("/") <= MAX_SKILL_FOLDER_DEPTH
            and PurePosixPath(relative_path).suffix.lower() in TEXT_FILE_EXTENSIONS
            and not entry["path"].startswith(nested_skill_prefixes)
        ):
            selected.append(entry)
    return selected


async def attach_skill_folder_files(
    client: GitLabClient,
    skills: list[tuple[dict[str, Any], str]],
    *,
    ref: str | None = None,
) -> list[dict[str, Any] | None]:
    """Set `skill.files` on each (skill raw item, SKILL.md content) pair.

    Folder files are read at `ref`, or at each skill's branch. A skill over the
    size limit comes back as None.
    """

    async def attach(skill_item: dict[str, Any], content: str) -> dict[str, Any] | None:
        files = await fetch_skill_folder_files(
            client,
            project=skill_item["repo"],
            ref=ref or skill_item["__branch"],
            skill_md_path=skill_item["skill"]["skillMdPath"],
            skill_md_size=len(content.encode("utf-8")),
        )
        if files is None:
            return None
        skill_item["skill"]["files"] = files
        return skill_item

    return await asyncio.gather(*(attach(item, content) for item, content in skills))


async def fetch_skill_folder_files(
    client: GitLabClient,
    *,
    project: dict[str, Any],
    ref: str,
    skill_md_path: str,
    skill_md_size: int,
) -> list[dict[str, str]] | None:
    """Fetch the text files in the skill folder at `ref` (branch or commit SHA),
    sorted by relative path.

    Returns None when SKILL.md plus its folder files exceed the bundle limit.
    GitLab trees carry no file sizes, so the limit is checked after download.
    """
    prefix = skill_dir_prefix(skill_md_path)
    tree: list[dict[str, Any]] = []
    async for batch in client.get_repository_tree(
        project, prefix.rstrip("/"), ref, recursive=True
    ):
        tree.extend(batch)
    entries = select_skill_folder_files(tree, skill_md_path)

    project_id = str(project["id"])
    contents = await asyncio.gather(
        *(_fetch_text_file(client, project_id, entry["path"], ref) for entry in entries)
    )
    files = {
        entry["path"]: content
        for entry, content in zip(entries, contents)
        if content is not None
    }

    bundle_size = skill_md_size + sum(
        len(content.encode("utf-8")) for content in files.values()
    )
    if bundle_size > MAX_SKILL_BUNDLE_SIZE:
        logger.warning(
            f"Skipping skill {skill_md_path} in {project.get('path_with_namespace')}"
            f"@{ref}: SKILL.md and its {len(files)} folder files total "
            f"{bundle_size} bytes, over the {MAX_SKILL_BUNDLE_SIZE} byte limit"
        )
        return None

    return [
        {"path": path.removeprefix(prefix), "content": content}
        for path, content in sorted(files.items())
    ]


async def _fetch_text_file(
    client: GitLabClient, project_id: str, file_path: str, ref: str
) -> str | None:
    try:
        return await client.rest.get_file_content(project_id, file_path, ref)
    except UnicodeDecodeError:
        logger.warning(f"Skipping non-UTF-8 skill folder file {file_path}")
        return None
