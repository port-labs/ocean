from port_ocean.context.ocean import ocean
from loguru import logger
from github.webhooks_processors.processors import (
    GithubPingWebhookProcessor,
    GithubIssueWebhookProcessor,
    GithubRepositoryWebhookProcessor,
    GithubPullRequestWebhookProcessor,
)



def register_webhook_processors(path: str = "/webhook") -> None:
    """
    Register all webhook processors for the given path.
    """
    logger.info(f"Registering webhook processors")

    print(f"#################################################register_webhook_processors path = {path}")

    ocean.add_webhook_processor(path, GithubIssueWebhookProcessor)
    ocean.add_webhook_processor(path, GithubPullRequestWebhookProcessor)
    ocean.add_webhook_processor(path, GithubRepositoryWebhookProcessor)
    ocean.add_webhook_processor(path, GithubPingWebhookProcessor)
    

    logger.info(f"Webhook processors registered for paths: {path} and {path}")