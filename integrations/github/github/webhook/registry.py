from port_ocean.context.ocean import ocean
from github.webhook.webhook_processors.folder_webhook_processor import (
    FolderWebhookProcessor,
)
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
from github.webhook.webhook_processors.team_member_webhook_processor import (
    TeamMemberWebhookProcessor,
)
from github.webhook.webhook_processors.team_webhook_processor import (
    TeamWebhookProcessor,
)
from github.webhook.webhook_processors.user_webhook_processor import (
    UserWebhookProcessor,
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
from github.webhook.webhook_processors.file_webhook_processor import (
    FileWebhookProcessor,
)
from github.webhook.webhook_processors.collaborator_webhook_processor import (
    CollaboratorMemberWebhookProcessor,
    CollaboratorMembershipWebhookProcessor,
    CollaboratorTeamWebhookProcessor,
)
from github.webhook.webhook_processors.check_runs.check_runs_validator_webhook_processor import (
    CheckRunValidatorWebhookProcessor,
)
from github.webhook.webhook_processors.secret_scanning_alert_webhook_processor import (
    SecretScanningAlertWebhookProcessor,
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
    ocean.add_webhook_processor(path, FolderWebhookProcessor)
    ocean.add_webhook_processor(path, TeamWebhookProcessor)
    ocean.add_webhook_processor(path, TeamMemberWebhookProcessor)
    ocean.add_webhook_processor(path, UserWebhookProcessor)
    ocean.add_webhook_processor(path, FileWebhookProcessor)
    ocean.add_webhook_processor(path, CollaboratorMemberWebhookProcessor)
    ocean.add_webhook_processor(path, CollaboratorMembershipWebhookProcessor)
    ocean.add_webhook_processor(path, CollaboratorTeamWebhookProcessor)
    ocean.add_webhook_processor(path, CheckRunValidatorWebhookProcessor)
    ocean.add_webhook_processor(path, SecretScanningAlertWebhookProcessor)
