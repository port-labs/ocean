from dataclasses import dataclass, field
from typing import Any

from port_ocean.integration_testing import ResyncResult

from mocks.payloads import (
    JIRA_API_URL,
    ISSUE_COUNT,
    PROJECT_KEYS,
    USER_COUNT,
    issue_response,
    user_response,
)


@dataclass(frozen=True)
class RawExpectation:
    """Expected raw item, located by its natural key.

    `fields` maps dotted raw paths (e.g. ``"fields.status.name"``) to values.
    """

    key: str
    fields: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KindExpectation:
    key_field: str
    count: int
    items: tuple[RawExpectation, ...]


def raw_field(item: dict[str, Any], path: str) -> Any:
    value: Any = item
    for part in path.split("."):
        assert (
            isinstance(value, dict) and part in value
        ), f"Raw item is missing field {path!r} (stopped at {part!r}): {item!r}"
        value = value[part]
    return value


def assert_raw_items(
    result: ResyncResult, kind: str, expectation: KindExpectation
) -> None:
    items = result.raw_items(kind)
    keys = [raw_field(item, expectation.key_field) for item in items]
    assert (
        len(items) == expectation.count
    ), f"Expected {expectation.count} raw {kind} items, got {len(items)}: {keys}"

    items_by_key = dict(zip(keys, items))
    expected_keys = {expected.key for expected in expectation.items}
    assert items_by_key.keys() == expected_keys, (
        f"Unexpected {expectation.key_field} values for kind {kind}. "
        f"expected={sorted(expected_keys)} actual={sorted(items_by_key)}"
    )
    for expected in expectation.items:
        item = items_by_key[expected.key]
        for path, value in expected.fields.items():
            actual = raw_field(item, path)
            assert actual == value, (
                f"{kind}/{expected.key} field {path!r} mismatch: "
                f"expected {value!r}, got {actual!r}"
            )


def _project_items() -> tuple[RawExpectation, ...]:
    return tuple(
        RawExpectation(
            key=key,
            fields={
                "name": f"Project {key}",
                # Port's `url` property is derived from the host in `self` + `key`.
                "self": f"{JIRA_API_URL}/project/{10000 + i}",
                "insight.totalIssueCount": i * 10,
            },
        )
        for i, key in enumerate(PROJECT_KEYS, start=1)
    )


def _issue_items() -> tuple[RawExpectation, ...]:
    items = []
    for i in range(1, ISSUE_COUNT + 1):
        record = issue_response(i)
        fields = record["fields"]
        items.append(
            RawExpectation(
                key=record["key"],
                fields={
                    "self": f"{JIRA_API_URL}/issue/{record['key']}",
                    "fields.summary": fields["summary"],
                    "fields.status.name": fields["status"]["name"],
                    "fields.issuetype.name": fields["issuetype"]["name"],
                    "fields.creator.emailAddress": fields["creator"]["emailAddress"],
                    "fields.priority.name": fields["priority"]["name"],
                    "fields.labels": fields["labels"],
                    "fields.created": fields["created"],
                    "fields.updated": fields["updated"],
                    "fields.project.key": fields["project"]["key"],
                    "fields.assignee.accountId": fields["assignee"]["accountId"],
                    "fields.reporter.accountId": fields["reporter"]["accountId"],
                },
            )
        )
    return tuple(items)


def _user_items() -> tuple[RawExpectation, ...]:
    items = []
    for i in range(1, USER_COUNT + 1):
        record = user_response(i)
        items.append(
            RawExpectation(
                key=record["accountId"],
                fields={
                    "displayName": record["displayName"],
                    "emailAddress": record["emailAddress"],
                    "active": record["active"],
                    "accountType": record["accountType"],
                    "timeZone": record["timeZone"],
                    "locale": record["locale"],
                    "avatarUrls.48x48": record["avatarUrls"]["48x48"],
                },
            )
        )
    return tuple(items)


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "project": KindExpectation(
        key_field="key", count=len(PROJECT_KEYS), items=_project_items()
    ),
    "issue": KindExpectation(key_field="key", count=ISSUE_COUNT, items=_issue_items()),
    "user": KindExpectation(
        key_field="accountId", count=USER_COUNT, items=_user_items()
    ),
}
