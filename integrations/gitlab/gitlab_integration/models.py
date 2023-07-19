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


class ObjectKind:
    ISSUE = "issue"
    JOB = "job"
    MERGE_REQUEST = "merge request"
    PIPELINE = "pipeline"
    PROJECT = "project"
