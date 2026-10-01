"""Vercel webhook event type constants."""


class VercelEventType:
    """Constants for Vercel webhook event types."""

    # Deployment events
    DEPLOYMENT_CREATED = "deployment.created"
    DEPLOYMENT_SUCCEEDED = "deployment.succeeded"
    DEPLOYMENT_READY = "deployment.ready"
    DEPLOYMENT_ERROR = "deployment.error"
    DEPLOYMENT_CANCELED = "deployment.canceled"
    DEPLOYMENT_PROMOTED = "deployment.promoted"
    DEPLOYMENT_DELETED = "deployment.deleted"

    # Project events
    PROJECT_CREATED = "project.created"
    PROJECT_REMOVED = "project.removed"

    # Domain events
    DOMAIN_CREATED = "domain.created"
    DOMAIN_DELETED = "domain.deleted"


# Map event types to resource kinds
EVENT_KIND_MAP: dict[str, str] = {
    VercelEventType.DEPLOYMENT_CREATED: "deployment",
    VercelEventType.DEPLOYMENT_SUCCEEDED: "deployment",
    VercelEventType.DEPLOYMENT_READY: "deployment",
    VercelEventType.DEPLOYMENT_ERROR: "deployment",
    VercelEventType.DEPLOYMENT_CANCELED: "deployment",
    VercelEventType.DEPLOYMENT_PROMOTED: "deployment",
    VercelEventType.DEPLOYMENT_DELETED: "deployment",
    VercelEventType.PROJECT_CREATED: "project",
    VercelEventType.PROJECT_REMOVED: "project",
    VercelEventType.DOMAIN_CREATED: "domain",
    VercelEventType.DOMAIN_DELETED: "domain",
}

# Events that represent deletions
DELETION_EVENTS: frozenset[str] = frozenset(
    {
        VercelEventType.DEPLOYMENT_DELETED,
        VercelEventType.PROJECT_REMOVED,
        VercelEventType.DOMAIN_DELETED,
    }
)
