from github.clients.http.mixin import GithubRestMixin
from github.clients.http.base_client import BaseGithubClient


class OrganizationGithubClient(GithubRestMixin, BaseGithubClient):
    """REST client (no organization required)."""

    pass
