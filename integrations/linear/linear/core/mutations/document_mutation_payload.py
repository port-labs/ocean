from pydantic import BaseModel, ConfigDict


class DocumentCreateMutationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    title: str
    content: str | None = None
    issueId: str | None = None
    projectId: str | None = None
