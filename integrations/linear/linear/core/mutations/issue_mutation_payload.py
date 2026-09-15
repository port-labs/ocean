from pydantic import BaseModel, ConfigDict


class IssueMutationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    priority: int | None = None


class IssueCreateMutationPayload(IssueMutationPayload):
    teamId: str
    title: str
    parentId: str | None = None
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    labelIds: list[str] | None = None


class IssueUpdateMutationPayload(IssueMutationPayload):
    title: str | None = None
    description: str | None = None
    assigneeId: str | None = None
    stateId: str | None = None
    projectId: str | None = None
    cycleId: str | None = None
    delegateId: str | None = None
    labelIds: list[str] | None = None
