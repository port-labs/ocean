from typing import Any

PAGERDUTY_API_URL = "https://api.pagerduty.com"
PAGERDUTY_TOKEN = "test-api-token"  # does not start with "pd" → Token auth, no OAuth round-trip

RECORD_COUNT = 2

SERVICE_IDS = [f"service-id-{i}" for i in range(1, RECORD_COUNT + 1)]
ESCALATION_POLICY_IDS = [f"ep-id-{i}" for i in range(1, RECORD_COUNT + 1)]
ONCALL_USER_IDS = [f"user-id-{i}" for i in range(1, RECORD_COUNT + 1)]
ONCALL_USER_EMAILS = [f"user{i}@example.com" for i in range(1, RECORD_COUNT + 1)]
ONCALL_USER_NAMES = [f"User {i}" for i in range(1, RECORD_COUNT + 1)]
INCIDENT_IDS = [f"incident-id-{i}" for i in range(1, RECORD_COUNT + 1)]
SCHEDULE_IDS = [f"schedule-id-{i}" for i in range(1, RECORD_COUNT + 1)]


def _pd_url(resource: str, resource_id: str) -> str:
    return f"https://example.pagerduty.com/{resource}/{resource_id}"


def service_response(idx: int) -> dict[str, Any]:
    return {
        "id": SERVICE_IDS[idx - 1],
        "name": f"Service {idx}",
        "status": "active",
        "html_url": _pd_url("services", SERVICE_IDS[idx - 1]),
        "escalation_policy": {
            "id": ESCALATION_POLICY_IDS[idx - 1],
            "summary": f"Escalation Policy {idx}",
        },
    }


def oncall_response(idx: int) -> dict[str, Any]:
    return {
        "user": {
            "id": ONCALL_USER_IDS[idx - 1],
            "name": ONCALL_USER_NAMES[idx - 1],
            "email": ONCALL_USER_EMAILS[idx - 1],
        },
        "schedule": {
            "id": SCHEDULE_IDS[idx - 1],
            "html_url": _pd_url("schedules", SCHEDULE_IDS[idx - 1]),
        },
        "escalation_policy": {
            "id": ESCALATION_POLICY_IDS[idx - 1],
        },
        "escalation_level": 1,
        "start": f"2024-01-0{idx}T00:00:00Z",
        "end": f"2024-01-{idx + 7:02d}T00:00:00Z",
    }


def incident_response(idx: int) -> dict[str, Any]:
    return {
        "id": INCIDENT_IDS[idx - 1],
        "title": f"Incident {idx}",
        "status": "triggered",
        "html_url": _pd_url("incidents", INCIDENT_IDS[idx - 1]),
        "urgency": "high",
        "assignments": [
            {
                "assignee": {
                    "email": ONCALL_USER_EMAILS[idx - 1],
                    "id": ONCALL_USER_IDS[idx - 1],
                }
            }
        ],
        "escalation_policy": {
            "summary": f"Escalation Policy {idx}",
            "id": ESCALATION_POLICY_IDS[idx - 1],
        },
        "created_at": f"2024-01-0{idx}T00:00:00Z",
        "updated_at": f"2024-01-0{idx}T01:00:00Z",
        "priority": None,
        "description": f"Test incident {idx}",
        "first_trigger_log_entry": {"agent": {"summary": ONCALL_USER_NAMES[idx - 1]}},
        "service": {"id": SERVICE_IDS[idx - 1]},
    }


def schedule_response(idx: int) -> dict[str, Any]:
    return {
        "id": SCHEDULE_IDS[idx - 1],
        "name": f"Schedule {idx}",
        "html_url": _pd_url("schedules", SCHEDULE_IDS[idx - 1]),
        "time_zone": "America/New_York",
        "description": f"Test schedule {idx}",
        "users": [
            {
                "id": ONCALL_USER_IDS[idx - 1],
                "name": ONCALL_USER_NAMES[idx - 1],
            }
        ],
    }


def escalation_policy_response(idx: int) -> dict[str, Any]:
    return {
        "id": ESCALATION_POLICY_IDS[idx - 1],
        "name": f"Escalation Policy {idx}",
        "html_url": _pd_url("escalation_policies", ESCALATION_POLICY_IDS[idx - 1]),
        "summary": f"Description {idx}",
        "escalation_rules": [],
    }


def user_response(idx: int) -> dict[str, Any]:
    return {
        "id": ONCALL_USER_IDS[idx - 1],
        "name": ONCALL_USER_NAMES[idx - 1],
        "html_url": _pd_url("users", ONCALL_USER_IDS[idx - 1]),
        "time_zone": "America/New_York",
        "email": ONCALL_USER_EMAILS[idx - 1],
        "description": f"Test user {idx}",
        "role": "user",
        "job_title": f"Engineer {idx}",
        "teams": [],
        "contact_methods": [],
    }


def paginated(resource_name: str, records: list[dict[str, Any]]) -> dict[str, Any]:
    """Wrap records in the PagerDuty classic pagination envelope (no next page)."""
    return {resource_name: records, "more": False, "limit": 100, "offset": 0}
