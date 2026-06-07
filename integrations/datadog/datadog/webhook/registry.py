from port_ocean.context.ocean import ocean

from datadog.webhook.webhook_client import (
    AUDIT_TRAIL_WEBHOOK_PATH,
    MONITOR_WEBHOOK_PATH,
)
from datadog.webhook.webhook_processors.audit_trails.monitor_webhook_processor import (
    MonitorWebhookProcessor as AuditMonitorWebhookProcessor,
)
from datadog.webhook.webhook_processors.audit_trails.role_webhook_processor import (
    RoleWebhookProcessor,
)
from datadog.webhook.webhook_processors.audit_trails.slo_webhook_processor import (
    SloWebhookProcessor,
)
from datadog.webhook.webhook_processors.audit_trails.team_webhook_processor import (
    TeamWebhookProcessor,
)
from datadog.webhook.webhook_processors.audit_trails.user_webhook_processor import (
    UserWebhookProcessor,
)
from datadog.webhook.webhook_processors.monitor_events.monitor_webhook_processor import (
    MonitorWebhookProcessor,
)
from datadog.webhook.webhook_processors.monitor_events.service_dependency_webhook_processor import (
    ServiceDependencyWebhookProcessor,
)


def register_live_events_webhooks() -> None:
    ocean.add_webhook_processor(MONITOR_WEBHOOK_PATH, MonitorWebhookProcessor)
    ocean.add_webhook_processor(MONITOR_WEBHOOK_PATH, ServiceDependencyWebhookProcessor)
    ocean.add_webhook_processor(AUDIT_TRAIL_WEBHOOK_PATH, AuditMonitorWebhookProcessor)
    ocean.add_webhook_processor(AUDIT_TRAIL_WEBHOOK_PATH, UserWebhookProcessor)
    ocean.add_webhook_processor(AUDIT_TRAIL_WEBHOOK_PATH, TeamWebhookProcessor)
    ocean.add_webhook_processor(AUDIT_TRAIL_WEBHOOK_PATH, SloWebhookProcessor)
    ocean.add_webhook_processor(AUDIT_TRAIL_WEBHOOK_PATH, RoleWebhookProcessor)
