WEBHOOK_PATH_SUFFIX = "/integration/webhook"
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
WEBHOOK_TARGET_VERSION = "2026-09-11"
SIGNATURE_HEADER = "plain-request-signature"

# Canonical event types from Plain webhook schema 2026-09-11.
THREAD_UPSERT_EVENTS = frozenset(
    {
        "thread.thread_created",
        "thread.thread_status_transitioned",
        "thread.thread_assignment_transitioned",
        "thread.thread_labels_changed",
        "thread.thread_priority_changed",
        "thread.thread_field_created",
        "thread.thread_field_updated",
        "thread.thread_field_deleted",
        "thread.thread_tenant_updated",
        "thread.thread_locked",
    }
)

THREAD_MESSAGE_EVENTS = frozenset(
    {
        "timeline.timeline_entry_changed",
        "thread.email_received",
        "thread.email_sent",
        "thread.chat_received",
        "thread.chat_sent",
        "thread.slack_message_received",
        "thread.slack_message_sent",
        "thread.slack_message_updated",
        "thread.discord_message_received",
        "thread.discord_message_sent",
        "thread.discord_message_updated",
        "thread.ms_teams_message_received",
        "thread.ms_teams_message_sent",
        "thread.note_created",
        "thread.note_mention_created",
    }
)

CUSTOMER_UPSERT_EVENTS = frozenset(
    {
        "customer.customer_created",
        "customer.customer_updated",
        "customer.customer_changed",
    }
)
CUSTOMER_DELETE_EVENTS = frozenset({"customer.customer_deleted"})
CUSTOMER_EVENTS = CUSTOMER_UPSERT_EVENTS | CUSTOMER_DELETE_EVENTS

DISCUSSION_EVENTS = frozenset(
    {
        "discussion.discussion_created",
        "discussion.message_created",
        "discussion.tool_call_approval_requested",
        "discussion.tool_call_approval_resolved",
    }
)
DISCUSSION_MESSAGE_EVENTS = frozenset({"discussion.message_created"})

COMPANY_EVENTS = CUSTOMER_UPSERT_EVENTS
TENANT_EVENTS = frozenset({"thread.thread_tenant_updated"})
USER_EVENTS = frozenset({"thread.thread_assignment_transitioned"})
MACHINE_USER_EVENTS = frozenset({"thread.thread_assignment_transitioned"})

WEBHOOK_EVENT_TYPES = sorted(
    THREAD_UPSERT_EVENTS
    | THREAD_MESSAGE_EVENTS
    | CUSTOMER_EVENTS
    | DISCUSSION_EVENTS
    | DISCUSSION_MESSAGE_EVENTS
    | COMPANY_EVENTS
    | TENANT_EVENTS
    | USER_EVENTS
    | MACHINE_USER_EVENTS
)
