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

WEBHOOK_PATH = "/webhook"

def register_live_events_webhooks() -> None:
    """Register all live event webhook processors."""
    ocean.add_webhook_processor(WEBHOOK_PATH, RepositoryWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, PullRequestWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, IssueWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, ReleaseWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, TagWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, BranchWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, EnvironmentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, DeploymentWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, WorkflowRunWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, WorkflowWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, DependabotAlertWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, CodeScanningAlertWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, FolderWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, TeamWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, TeamMemberWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, UserWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, FileWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, CollaboratorMemberWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, CollaboratorMembershipWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, CollaboratorTeamWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, CheckRunValidatorWebhookProcessor)
    ocean.add_webhook_processor(WEBHOOK_PATH, SecretScanningAlertWebhookProcessor)
