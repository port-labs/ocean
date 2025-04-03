from github_cloud.client import GitHubClient
from github_cloud.helpers.exceptions import MissingIntegrationCredentialException
from port_ocean.context.ocean import ocean

def init_client() -> GitHubClient:
    """Initialize GitHub client with credentials from integration config."""
    token = ocean.integration_config.get("github_access_token")
    organization = ocean.integration_config.get("github_organization")
    base_url = ocean.integration_config.get("github_base_url", "https://api.github.com")
    
    if not token or not organization:
        raise MissingIntegrationCredentialException("Missing GitHub token or organization")
        
    return GitHubClient(token, organization, base_url)
