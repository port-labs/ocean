from github.actions.abstract_github_executor import AbstractGithubExecutor
from github.clients.client_factory import create_github_client_for_org
from github.clients.http.rest_client import GithubRestClient
from port_ocean.core.models import IntegrationRun


class AbstractExternalCustomPropertiesExecutor(AbstractGithubExecutor):
    """Custom-property actions use GitHub App installation tokens only.

    `/orgs/{org}/properties/installations/values` is an installation endpoint.
    Identity-propagated user OAuth tokens only have the `repo` scope and cannot
    call it.
    """

    async def _rest_client_for_org(
        self, run: IntegrationRun, organization: str
    ) -> GithubRestClient:
        return await create_github_client_for_org(organization)
