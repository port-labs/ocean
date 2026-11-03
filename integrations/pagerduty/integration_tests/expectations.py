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


class _Absent:
    def __repr__(self) -> str:
        return "<absent>"


ABSENT = _Absent()


def raw_field(item: Any, path: str) -> Any:
    """Read a dotted path (numeric segments index lists) from a raw item, or ABSENT."""
    value = item
    for segment in path.split("."):
        if isinstance(value, list) and segment.isdigit():
            index = int(segment)
            if index >= len(value):
                return ABSENT
            value = value[index]
        elif isinstance(value, dict) and segment in value:
            value = value[segment]
        else:
            return ABSENT
    return value


@dataclass(frozen=True)
class RawExpectation:
    key: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KindExpectation:
    key_field: str
    records: tuple[RawExpectation, ...]


def assert_raw_items(
    items: list[dict[str, Any]], expectation: KindExpectation, kind: str
) -> None:
    by_key: dict[Any, dict[str, Any]] = {}
    for item in items:
        key = raw_field(item, expectation.key_field)
        assert key not in by_key, f"[{kind}] duplicate raw item for key {key!r}"
        by_key[key] = item

    expected_keys = {record.key for record in expectation.records}
    assert by_key.keys() == expected_keys, (
        f"[{kind}] unexpected raw item keys: "
        f"expected={sorted(expected_keys)} actual={sorted(map(str, by_key))}"
    )

    for record in expectation.records:
        item = by_key[record.key]
        for path, value in record.fields.items():
            actual = raw_field(item, path)
            assert actual == value, (
                f"[{kind}] raw field {path!r} for {record.key!r}: "
                f"expected {value!r}, got {actual!r}"
            )


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "services": KindExpectation(
        key_field="id",
        records=tuple(
            RawExpectation(
                key=SERVICE_IDS[i - 1],
                fields={
                    "name": service_response(i)["name"],
                    "status": "active",
                    "html_url": service_response(i)["html_url"],
                    # A single on-call at level 1: primary on-call, no secondary.
                    "__oncall_user": [oncall_response(i)],
                    "__oncall_user.0.user.email": ONCALL_USER_EMAILS[i - 1],
                    "__oncall_user.0.escalation_level": 1,
                    # serviceAnalytics is disabled in the selector.
                    "__analytics": ABSENT,
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "incidents": KindExpectation(
        key_field="id",
        records=tuple(
            RawExpectation(
                key=INCIDENT_IDS[i - 1],
                fields={
                    "title": incident_response(i)["title"],
                    "status": "triggered",
                    "html_url": incident_response(i)["html_url"],
                    "urgency": "high",
                    "assignments": [
                        {
                            "assignee": {
                                "email": ONCALL_USER_EMAILS[i - 1],
                                "id": ONCALL_USER_IDS[i - 1],
                            }
                        }
                    ],
                    "escalation_policy.summary": f"Escalation Policy {i}",
                    "created_at": f"2024-01-0{i}T00:00:00Z",
                    "updated_at": f"2024-01-0{i}T01:00:00Z",
                    "priority": None,
                    "description": f"Test incident {i}",
                    "first_trigger_log_entry.agent.summary": ONCALL_USER_NAMES[i - 1],
                    "service.id": SERVICE_IDS[i - 1],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "schedules": KindExpectation(
        key_field="id",
        records=tuple(
            RawExpectation(
                key=SCHEDULE_IDS[i - 1],
                fields={
                    "name": schedule_response(i)["name"],
                    "html_url": schedule_response(i)["html_url"],
                    "time_zone": "America/New_York",
                    "description": f"Test schedule {i}",
                    "users": [
                        {
                            "id": ONCALL_USER_IDS[i - 1],
                            "name": ONCALL_USER_NAMES[i - 1],
                            "__email": ONCALL_USER_EMAILS[i - 1],
                        }
                    ],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "oncalls": KindExpectation(
        key_field="user.id",
        records=tuple(
            RawExpectation(
                key=ONCALL_USER_IDS[i - 1],
                fields={
                    "user.name": ONCALL_USER_NAMES[i - 1],
                    "user.email": ONCALL_USER_EMAILS[i - 1],
                    "schedule.id": SCHEDULE_IDS[i - 1],
                    "schedule.html_url": oncall_response(i)["schedule"]["html_url"],
                    "escalation_policy.id": ESCALATION_POLICY_IDS[i - 1],
                    "start": oncall_response(i)["start"],
                    "end": oncall_response(i)["end"],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "escalation_policies": KindExpectation(
        key_field="id",
        records=tuple(
            RawExpectation(
                key=ESCALATION_POLICY_IDS[i - 1],
                fields={
                    "name": escalation_policy_response(i)["name"],
                    "html_url": escalation_policy_response(i)["html_url"],
                    "summary": f"Description {i}",
                    "escalation_rules": [],
                    "__oncall_users": [oncall_response(i)],
                    "__oncall_users.0.user.email": ONCALL_USER_EMAILS[i - 1],
                    "__oncall_users.0.escalation_level": 1,
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "users": KindExpectation(
        key_field="id",
        records=tuple(
            RawExpectation(
                key=ONCALL_USER_IDS[i - 1],
                fields={
                    "name": ONCALL_USER_NAMES[i - 1],
                    "html_url": user_response(i)["html_url"],
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
