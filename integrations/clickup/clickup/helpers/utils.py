from enum import StrEnum
from typing import NamedTuple, Optional


class ObjectKind(StrEnum):
    """Enumeration of ClickUp object kinds following the hierarchy:
    Workspace → Space → Folder → List → Task
    """

    WORKSPACE = "workspace"
    SPACE = "space"
    FOLDER = "folder"
    LIST = "list"
    TASK = "task"


class IgnoredError(NamedTuple):
    """Represents an error that should be ignored during API requests."""

    status: int | str
    message: Optional[str] = None
