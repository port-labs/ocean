from dataclasses import dataclass, field
from typing import Any

from mocks.payloads import (
    JIRA_HOST,
    ISSUE_COUNT,
    PROJECT_KEYS,
    USER_COUNT,
    issue_response,
    project_response,
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
    entities: tuple[EntityExpectation, ...]


def _project_url(key: str, idx: int) -> str:
    return f"{JIRA_HOST}/projects/{key}"


def _issue_url(key: str) -> str:
    return f"{JIRA_HOST}/browse/{key}"


def _project_entities() -> tuple[EntityExpectation, ...]:
    return tuple(
        EntityExpectation(
            identifier=key,
            title=f"Project {key}",
            properties={
                "url": _project_url(key, i),
                "totalIssues": i * 10,
            },
        )
        for i, key in enumerate(PROJECT_KEYS, start=1)
    )


def _issue_entities() -> tuple[EntityExpectation, ...]:
    entities = []
    for i in range(1, ISSUE_COUNT + 1):
        record = issue_response(i)
        key = record["key"]
        entities.append(
            EntityExpectation(
                identifier=key,
                title=record["fields"]["summary"],
                properties={
                    "url": _issue_url(key),
                    "status": record["fields"]["status"]["name"],
                    "issueType": record["fields"]["issuetype"]["name"],
                    "creator": record["fields"]["creator"]["emailAddress"],
                    "priority": record["fields"]["priority"]["name"],
                    "labels": record["fields"]["labels"],
                    "created": record["fields"]["created"],
                    "updated": record["fields"]["updated"],
                },
                relations={
                    "project": record["fields"]["project"]["key"],
                    "assignee": record["fields"]["assignee"]["accountId"],
                    "reporter": record["fields"]["reporter"]["accountId"],
                },
            )
        )
    return tuple(entities)


def _user_entities() -> tuple[EntityExpectation, ...]:
    entities = []
    for i in range(1, USER_COUNT + 1):
        record = user_response(i)
        entities.append(
            EntityExpectation(
                identifier=record["accountId"],
                title=record["displayName"],
                properties={
                    "emailAddress": record["emailAddress"],
                    "active": record["active"],
                    "accountType": record["accountType"],
                    "timeZone": record["timeZone"],
                    "locale": record["locale"],
                    "avatarUrl": record["avatarUrls"]["48x48"],
                },
            )
        )
    return tuple(entities)


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "project": KindExpectation(
        count=len(PROJECT_KEYS),
        entities=_project_entities(),
    ),
    "issue": KindExpectation(
        count=ISSUE_COUNT,
        entities=_issue_entities(),
    ),
    "user": KindExpectation(
        count=USER_COUNT,
        entities=_user_entities(),
    ),
}
