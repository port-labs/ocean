from port_ocean.context.ocean import ocean
from github.client import GitHubClient

def create_github_client() -> GitHubClient:
    webhook_secret = ocean.integration_config.get("webhookSecret")
    return GitHubClient(
        base_url=ocean.integration_config.get("githubBaseUrl", "https://api.github.com"),
        token=ocean.integration_config["githubToken"],
        org_name=ocean.integration_config.get("orgName"),
        webhook_secret=webhook_secret,
    )