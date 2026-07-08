from dataclasses import dataclass, field
from typing import Any

from mocks.payloads import (
    ESCALATION_POLICY_IDS,
    INCIDENT_IDS,
    ONCALL_USER_EMAILS,
    ONCALL_USER_IDS,
    ONCALL_USER_NAMES,
    RECORD_COUNT,
    SCHEDULE_IDS,
    SERVICE_IDS,
    escalation_policy_response,
    incident_response,
    oncall_response,
    schedule_response,
    service_response,
    user_response,
)


@dataclass(frozen=True)
class EntityExpectation:
    identifier: str
    title: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    relations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KindExpectation:
    count: int
    blueprint: str
    entities: tuple[EntityExpectation, ...]


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "services": KindExpectation(
        count=RECORD_COUNT,
        blueprint="pagerdutyService",
        entities=tuple(
            EntityExpectation(
                identifier=SERVICE_IDS[i - 1],
                title=service_response(i)["name"],
                properties={
                    "status": "active",
                    "url": service_response(i)["html_url"],
                    "oncall": ONCALL_USER_EMAILS[i - 1],
                    "secondaryOncall": None,
                    "escalationLevels": 1,
                    "meanSecondsToResolve": None,
                    "meanSecondsToFirstAck": None,
                    "meanSecondsToEngage": None,
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "incidents": KindExpectation(
        count=RECORD_COUNT,
        blueprint="pagerdutyIncident",
        entities=tuple(
            EntityExpectation(
                identifier=INCIDENT_IDS[i - 1],
                title=incident_response(i)["title"],
                properties={
                    "status": "triggered",
                    "url": incident_response(i)["html_url"],
                    "urgency": "high",
                    "assignees": [ONCALL_USER_EMAILS[i - 1]],
                    "escalation_policy": f"Escalation Policy {i}",
                    "created_at": f"2024-01-0{i}T00:00:00Z",
                    "updated_at": f"2024-01-0{i}T01:00:00Z",
                    "priority": None,
                    "description": f"Test incident {i}",
                    "triggered_by": ONCALL_USER_NAMES[i - 1],
                },
                relations={"pagerdutyService": SERVICE_IDS[i - 1]},
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "schedules": KindExpectation(
        count=RECORD_COUNT,
        blueprint="pagerdutySchedule",
        entities=tuple(
            EntityExpectation(
                identifier=SCHEDULE_IDS[i - 1],
                title=schedule_response(i)["name"],
                properties={
                    "url": schedule_response(i)["html_url"],
                    "timezone": "America/New_York",
                    "description": f"Test schedule {i}",
                    "users": [ONCALL_USER_EMAILS[i - 1]],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "oncalls": KindExpectation(
        count=RECORD_COUNT,
        blueprint="pagerdutyOncall",
        entities=tuple(
            EntityExpectation(
                identifier=f"{ONCALL_USER_IDS[i - 1]}-{SCHEDULE_IDS[i - 1]}-{oncall_response(i)['start']}",
                title=ONCALL_USER_NAMES[i - 1],
                properties={
                    "user": ONCALL_USER_EMAILS[i - 1],
                    "startDate": oncall_response(i)["start"],
                    "endDate": oncall_response(i)["end"],
                    "url": oncall_response(i)["schedule"]["html_url"],
                },
                relations={
                    "pagerdutySchedule": SCHEDULE_IDS[i - 1],
                    "pagerdutyEscalationPolicy": ESCALATION_POLICY_IDS[i - 1],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "escalation_policies": KindExpectation(
        count=RECORD_COUNT,
        blueprint="pagerdutyEscalationPolicy",
        entities=tuple(
            EntityExpectation(
                identifier=ESCALATION_POLICY_IDS[i - 1],
                title=escalation_policy_response(i)["name"],
                properties={
                    "url": escalation_policy_response(i)["html_url"],
                    "description": f"Description {i}",
                    "primaryOncall": None,
                    "escalationRules": [],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "users": KindExpectation(
        count=RECORD_COUNT,
        blueprint="pagerdutyUser",
        entities=tuple(
            EntityExpectation(
                identifier=ONCALL_USER_IDS[i - 1],
                title=ONCALL_USER_NAMES[i - 1],
                properties={
                    "url": user_response(i)["html_url"],
                    "time_zone": "America/New_York",
                    "email": ONCALL_USER_EMAILS[i - 1],
                    "description": f"Test user {i}",
                    "role": "user",
                    "job_title": f"Engineer {i}",
                    "teams": [],
                    "contact_methods": [],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
}
