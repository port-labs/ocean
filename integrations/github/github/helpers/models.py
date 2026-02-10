from pydantic import BaseModel, Field


class RepoSearchParams(BaseModel):
    query: str = Field(default_factory=str)
