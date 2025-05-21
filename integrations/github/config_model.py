from pydantic import BaseModel

class MyConfig(BaseModel):
    """Configuration model for GitHub integration."""
    github_token: str
    github_org: str
    github_repo: str