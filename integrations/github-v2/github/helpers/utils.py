from enum import StrEnum
from loguru import logger
from typing import Any, Union
import json
import yaml


class ObjectKind(StrEnum):
    """Kinds of GitHub objects supported by the integration."""
    REPOSITORY = "repository"
    PULL_REQUEST = "pull-request"
    TEAM = "team"
    USER = "user"
    ISSUE = "issue"
    WORKFLOW = "workflow"
