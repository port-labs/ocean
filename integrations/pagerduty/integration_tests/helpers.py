from typing import Any

from mocks.payloads import PAGERDUTY_API_URL, PAGERDUTY_TOKEN

_SERVICES_RESOURCE: dict[str, Any] = {
    "kind": "services",
    "selector": {
        "query": "true",
        "serviceAnalytics": "false",
    },
    "port": {
        "entity": {
            "mappings": {
                "identifier": ".id",
                "title": ".name",
                "blueprint": '"pagerdutyService"',
                "properties": {
                    "status": ".status",
                    "url": ".html_url",
                    "oncall": ".__oncall_user | sort_by(.escalation_level) | .[0].user.email",
                    "secondaryOncall": ".__oncall_user | sort_by(.escalation_level) | .[1].user.email",
                    "escalationLevels": ".__oncall_user | map(.escalation_level) | unique | length",
                    "meanSecondsToResolve": ".__analytics.mean_seconds_to_resolve",
                    "meanSecondsToFirstAck": ".__analytics.mean_seconds_to_first_ack",
                    "meanSecondsToEngage": ".__analytics.mean_seconds_to_engage",
                },
            }
        }
    },
}

_INCIDENTS_TRIGGERED_RESOURCE: dict[str, Any] = {
    "kind": "incidents",
    "selector": {
        "query": "true",
        "apiQueryParams": {
            "include": ["assignees", "first_trigger_log_entries"],
            "statuses": ["triggered", "acknowledged"],
        },
    },
    "port": {
        "entity": {
            "mappings": {
                "identifier": ".id | tostring",
                "title": ".title",
                "blueprint": '"pagerdutyIncident"',
                "properties": {
                    "status": ".status",
                    "url": ".html_url",
                    "urgency": ".urgency",
                    "assignees": ".assignments | map(.assignee.email)",
                    "escalation_policy": ".escalation_policy.summary",
                    "created_at": ".created_at",
                    "updated_at": ".updated_at",
                    "priority": "if .priority != null then .priority.summary else null end",
                    "description": ".description",
                    "triggered_by": ".first_trigger_log_entry.agent.summary",
                },
                "relations": {
                    "pagerdutyService": ".service.id",
                },
            }
        }
    },
}

_INCIDENTS_RESOLVED_RESOURCE: dict[str, Any] = {
    "kind": "incidents",
    "selector": {
        "query": "true",
        "apiQueryParams": {
            "include": ["assignees", "first_trigger_log_entries"],
            "statuses": ["resolved"],
        },
    },
    "port": {
        "entity": {
            "mappings": {
                "identifier": ".id | tostring",
                "title": ".title",
                "blueprint": '"pagerdutyIncident"',
                "properties": {
                    "status": ".status",
                    "url": ".html_url",
                    "urgency": ".urgency",
                    "escalation_policy": ".escalation_policy.summary",
                    "created_at": ".created_at",
                    "updated_at": ".updated_at",
                    "priority": "if .priority != null then .priority.summary else null end",
                    "description": ".description",
                    "triggered_by": ".first_trigger_log_entry.agent.summary",
                },
                "relations": {
                    "pagerdutyService": ".service.id",
                },
            }
        }
    },
}

_SCHEDULES_RESOURCE: dict[str, Any] = {
    "kind": "schedules",
    "selector": {"query": "true"},
    "port": {
        "entity": {
            "mappings": {
                "identifier": ".id",
                "title": ".name",
                "blueprint": '"pagerdutySchedule"',
                "properties": {
                    "url": ".html_url",
                    "timezone": ".time_zone",
                    "description": ".description",
                    "users": '[.users[] | select(has("__email")) | .__email]',
                },
            }
        }
    },
}

_ONCALLS_RESOURCE: dict[str, Any] = {
    "kind": "oncalls",
    "selector": {
        "query": "true",
        "apiQueryParams": {"include": ["users"]},
    },
    "port": {
        "entity": {
            "mappings": {
                "identifier": '.user.id + "-" + .schedule.id + "-" + .start',
                "title": ".user.name",
                "blueprint": '"pagerdutyOncall"',
                "properties": {
                    "user": ".user.email",
                    "startDate": ".start",
                    "endDate": ".end",
                    "url": ".schedule.html_url",
                },
                "relations": {
                    "pagerdutySchedule": ".schedule.id",
                    "pagerdutyEscalationPolicy": ".escalation_policy.id",
                },
            }
        }
    },
}

_ESCALATION_POLICIES_RESOURCE: dict[str, Any] = {
    "kind": "escalation_policies",
    "selector": {
        "query": "true",
        "attachOncallUsers": "false",
    },
    "port": {
        "entity": {
            "mappings": {
                "identifier": ".id",
                "title": ".name",
                "blueprint": '"pagerdutyEscalationPolicy"',
                "properties": {
                    "url": ".html_url",
                    "description": ".summary",
                    "primaryOncall": ".__oncall_users | sort_by(.escalation_level) | .[0].user.email",
                    "escalationRules": ".escalation_rules",
                },
            }
        }
    },
}

_USERS_RESOURCE: dict[str, Any] = {
    "kind": "users",
    "selector": {"query": "true"},
    "port": {
        "entity": {
            "mappings": {
                "identifier": ".id",
                "title": ".name",
                "blueprint": '"pagerdutyUser"',
                "properties": {
                    "url": ".html_url",
                    "time_zone": ".time_zone",
                    "email": ".email",
                    "description": ".description",
                    "role": ".role",
                    "job_title": ".job_title",
                    "teams": ".teams",
                    "contact_methods": ".contact_methods",
                },
            }
        }
    },
}

_RESOURCES_BY_KIND: dict[str, dict[str, Any]] = {
    "services": _SERVICES_RESOURCE,
    "incidents": _INCIDENTS_TRIGGERED_RESOURCE,
    "schedules": _SCHEDULES_RESOURCE,
    "oncalls": _ONCALLS_RESOURCE,
    "escalation_policies": _ESCALATION_POLICIES_RESOURCE,
    "users": _USERS_RESOURCE,
}


def integration_config() -> dict[str, Any]:
    return {
        "integration": {
            "identifier": "test-pagerduty",
            "type": "pagerduty",
            "config": {
                "token": PAGERDUTY_TOKEN,
                "api_url": PAGERDUTY_API_URL,
            },
        }
    }


def mapping_for_kind(kind: str) -> dict[str, Any]:
    return {
        "createMissingRelatedEntities": True,
        "deleteDependentEntities": True,
        "resources": [_RESOURCES_BY_KIND[kind]],
    }


def full_mapping_config() -> dict[str, Any]:
    return {
        "createMissingRelatedEntities": True,
        "deleteDependentEntities": True,
        "resources": [
            _SERVICES_RESOURCE,
            _INCIDENTS_TRIGGERED_RESOURCE,
            _INCIDENTS_RESOLVED_RESOURCE,
            _SCHEDULES_RESOURCE,
            _ONCALLS_RESOURCE,
            _ESCALATION_POLICIES_RESOURCE,
            _USERS_RESOURCE,
        ],
    }
