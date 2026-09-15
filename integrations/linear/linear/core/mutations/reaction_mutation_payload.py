from pydantic import BaseModel, ConfigDict


class ReactionCreateMutationPayload(BaseModel):
    model_config = ConfigDict(extra="ignore")

    issueId: str
    emoji: str
