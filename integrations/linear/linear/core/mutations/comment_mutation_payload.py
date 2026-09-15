from pydantic import BaseModel, ConfigDict


class CommentCreateMutationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issueId: str
    body: str
