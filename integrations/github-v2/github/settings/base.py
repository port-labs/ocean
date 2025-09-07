from pydantic import BaseModel

from .get_env import _cfg


class GithubSettings(BaseModel):
    base_url: str|None = _cfg("githubHost", "github_host")
    token: str|None = _cfg("githubToken", "github_token")
    organization: str|None = _cfg("githubOrganization", "github_organization")
    user: str|None = _cfg("githubUser", "github_user")
    webhook_secret: str|None = _cfg("webhookSecret", "webhook_secret")


# Singleton instance for convenience
SETTINGS = GithubSettings()
