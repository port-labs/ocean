from dataclasses import dataclass
from enum import Enum

from pydantic import BaseModel, Extra


class ContextProject(BaseModel, extra=Extra.allow):
    name: str
    id: int


class HookContext(BaseModel, extra=Extra.allow):
    event_name: str
    ref: str
    project: ContextProject
    before: str
    after: str


class ScopeType(Enum):
    Project = "project"
    Group = "group"


@dataclass
class Scope:
    type: ScopeType
    id: int


class ObjectKind:
    ISSUE = "issue"
    JOB = "job"
    MERGE_REQUEST = "merge request"
    PIPELINE = "pipeline"
    PROJECT = "project"
