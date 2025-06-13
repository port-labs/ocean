from port_ocean.context.ocean import ocean
from github.webhook.webhook_processors.repository_webhook_processor import (
    RepositoryWebhookProcessor,
)
from github.webhook.webhook_processors.pull_request_webhook_processor import (
    PullRequestWebhookProcessor,
)
from github.webhook.webhook_processors.issue_webhook_processor import (
    IssueWebhookProcessor,
)
from github.webhook.webhook_processors.release_webhook_processor import (
    ReleaseWebhookProcessor,
)
from github.webhook.webhook_processors.tag_webhook_processor import TagWebhookProcessor
from github.webhook.webhook_processors.branch_webhook_processor import (
    BranchWebhookProcessor,
)

from github.webhook.webhook_processors.environment_webhook_processor import (
    EnvironmentWebhookProcessor,
)
from github.webhook.webhook_processors.deployment_webhook_processor import (
    DeploymentWebhookProcessor,
)
from github.webhook.webhook_processors.workflow_run_webhook_processor import (
    WorkflowRunWebhookProcessor,
)
from github.webhook.webhook_processors.workflow_webhook_processor import (
    WorkflowWebhookProcessor,
)
from github.webhook.webhook_processors.dependabot_webhook_processor import (
    DependabotAlertWebhookProcessor,
)
from github.webhook.webhook_processors.code_scanning_alert_webhook_processor import (
    CodeScanningAlertWebhookProcessor,
)


def register_live_events_webhooks(path: str = "/webhook") -> None:
    """Register all live event webhook processors."""
    ocean.add_webhook_processor(path, RepositoryWebhookProcessor)
    ocean.add_webhook_processor(path, PullRequestWebhookProcessor)
    ocean.add_webhook_processor(path, IssueWebhookProcessor)
    ocean.add_webhook_processor(path, ReleaseWebhookProcessor)
    ocean.add_webhook_processor(path, TagWebhookProcessor)
    ocean.add_webhook_processor(path, BranchWebhookProcessor)
    ocean.add_webhook_processor(path, EnvironmentWebhookProcessor)
    ocean.add_webhook_processor(path, DeploymentWebhookProcessor)
    ocean.add_webhook_processor(path, WorkflowRunWebhookProcessor)
    ocean.add_webhook_processor(path, WorkflowWebhookProcessor)
    ocean.add_webhook_processor(path, DependabotAlertWebhookProcessor)
    ocean.add_webhook_processor(path, CodeScanningAlertWebhookProcessor)
