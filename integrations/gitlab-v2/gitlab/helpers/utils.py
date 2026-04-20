import json
import re
from copy import deepcopy
from enum import IntEnum
from enum import StrEnum
from typing import Any, Union

from loguru import logger
from yaml import YAMLError, safe_load

# GitLab project/group access-token bots have system-generated usernames like
# "project_<id>_bot_<hex>" or "group_<id>_bot_<hex>".  The members/all API
# does NOT return a `bot` field, so we fall back to pattern detection.
_BOT_USERNAME_RE = re.compile(r"^(?:project|group)_\d+_bot_[a-f0-9]+$")


def is_bot_member(member: dict[str, Any]) -> bool:
    """Return True when *member* looks like a GitLab bot / access-token user.

    Priority:
    1. Explicit ``bot=True`` from the API  → bot.
    2. Explicit ``bot=False`` from the API → not a bot (trust the API).
    3. ``bot`` field absent or ``None``    → fall back to username pattern.
       GitLab's /members/all endpoint omits the ``bot`` field for access-token
       users, so we detect them by their system-generated username format.
    """
    bot = member.get("bot")
    if bot is True:
        return True
    if bot is False:
        return False
    # bot field absent or None — fall back to username pattern
    username: str = member.get("username") or ""
    return bool(_BOT_USERNAME_RE.match(username))


class ObjectKind(StrEnum):
    PROJECT = "project"
    GROUP = "group"
    ISSUE = "issue"
    MERGE_REQUEST = "merge-request"
    GROUP_WITH_MEMBERS = "group-with-members"
    PROJECT_WITH_MEMBERS = "project-with-members"
    MEMBER = "member"
    FILE = "file"
    PIPELINE = "pipeline"
    JOB = "job"
    FOLDER = "folder"
    TAG = "tag"
    RELEASE = "release"


def parse_file_content(
    content: str,
    file_path: str,
    context: str,
) -> Union[str, dict[str, Any], list[Any]]:
    """
    Attempt to parse a string as JSON or YAML. If both parse attempts fail or the content
    is empty, the function returns the original string.

    :param content:    The raw file content to parse.
    :param file_path:  Optional file path for logging purposes (default: 'unknown').
    :param context:    Optional contextual info for logging purposes (default: 'unknown').
    :return:           A dictionary or list (if parsing was successful),
                       or the original string if parsing fails.
    """
    # Quick check for empty or whitespace-only strings
    if not content.strip():
        logger.debug(
            f"File '{file_path}' in '{context}' is empty; returning raw content."
        )
        return content

    try:
        return json.loads(content)
    except json.JSONDecodeError:
        pass

    # 2) Try YAML
    logger.debug(f"Attempting to parse file '{file_path}' in '{context}' as YAML.")
    try:
        parts = [x for x in content.split("\n---\n") if x.strip() != ""]
        documents = []
        for part in parts:
            # prevent oom
            data = deepcopy(safe_load(part))
            if isinstance(data, list):
                documents.extend(data)
            else:
                documents.append(data)

        return documents

    except YAMLError:
        logger.debug(
            f"Failed to parse file '{file_path}' in '{context}' as JSON or YAML. "
            "Returning raw content."
        )
        return content


def build_search_query(search_path: str) -> str:
    """Build a GitLab search query string from a file path pattern.

    The query always includes a ``filename:`` modifier so results are filtered
    by file name rather than just file contents.  When a directory component is
    present a ``path:`` modifier is also appended.  Glob characters (``*``) are
    stripped from the keyword because GitLab does not support them there, but
    they are preserved inside the ``filename:`` and ``path:`` modifiers.

    Examples:
        ``readme.md``            -> ``readme.md filename:readme.md``
        ``src/config/app.json``  -> ``app.json path:src/config filename:app.json``
        ``home/directory/*.txt`` -> ``.txt path:home/directory filename:*.txt``
        ``home/*/*.txt``         -> ``.txt path:home/* filename:*.txt``
    """
    if "/" not in search_path:
        keyword = search_path.replace("*", "")
        return f"{keyword} filename:{search_path}"
    directory, filename = search_path.rsplit("/", 1)
    keyword = filename.replace("*", "")
    return f"{keyword} path:{directory} filename:{filename}"


def enrich_resources_with_project(
    resources: list[dict[str, Any]], project_map: dict[str, Any]
) -> list[dict[str, Any]]:
    """
    Enrich resources with their corresponding project data.

    Args:
        resources: List of resources that have a 'project_id' field
        project_map: Dictionary mapping project IDs to project data

    Returns:
        List of resources enriched with '__project' field containing project data.
        Resources without matching projects are included with '__project' set to None.
    """
    enriched_resources = []
    for resource in resources:
        project_id = str(resource["project_id"])
        enriched_resource = {**resource, "__project": project_map.get(project_id)}
        enriched_resources.append(enriched_resource)
    return enriched_resources


class GitlabAccessLevel(IntEnum):
    GUEST = 10
    REPORTER = 20
    DEVELOPER = 30
    MAINTAINER = 40
    OWNER = 50
