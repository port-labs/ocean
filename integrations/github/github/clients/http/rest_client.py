from github.clients.http.base_client import AbstractGithubClient
from github.clients.http.mixin import GithubRestMixin


PAGE_SIZE = 100


class GithubRestClient(GithubRestMixin, AbstractGithubClient):
    """Org-scoped REST client (requires organization)."""

    pass
