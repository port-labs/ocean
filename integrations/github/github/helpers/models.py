from pydantic import BaseModel, Field


class RepoSearchParams(BaseModel):
    query: str = Field(
        title="Query",
        default_factory=str,
        description="GitHub repository search query (e.g. 'org:myorg' or 'topic:security').",
    )
