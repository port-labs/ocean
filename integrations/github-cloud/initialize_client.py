from port_ocean.context.ocean import ocean
from client import GithubClient
# from github_cloud.webhook_processors.abstract_webhook_processor import GithubWebhookClient


def init_client() -> GithubClient:
    return GithubClient.create_from_ocean_config()


# def init_webhook_client() -> GithubWebhookClient:
#     return GithubWebhookClient(
#         secret=ocean.integration_config["webhook_secret"],
#         workspace=ocean.integration_config["github_workspace"],
#         host=ocean.integration_config["github_host_url"],
#     )
