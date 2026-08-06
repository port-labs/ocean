from dataclasses import dataclass, field
from typing import Any

from mocks.payloads import (
    RECORD_COUNT,
    created_on_iso,
    sys_id,
    incident_response,
    service_catalog_response,
    user_group_response,
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


def _group_entities() -> tuple[EntityExpectation, ...]:
    entities = []
    for i in range(1, RECORD_COUNT + 1):
        record = user_group_response(i)
        entities.append(
            EntityExpectation(
                identifier=sys_id("group", i),
                title=record["name"],
                properties={
                    "description": record["description"],
                    "isActive": record["active"],
                    "createdOn": created_on_iso(i),
                    "createdBy": record["sys_created_by"],
                },
            )
        )
    return tuple(entities)


def _catalog_entities() -> tuple[EntityExpectation, ...]:
    entities = []
    for i in range(1, RECORD_COUNT + 1):
        record = service_catalog_response(i)
        entities.append(
            EntityExpectation(
                identifier=sys_id("catalog", i),
                title=record["title"],
                properties={
                    "description": record["description"],
                    "isActive": record["active"],
                    "createdOn": created_on_iso(i),
                    "createdBy": record["sys_created_by"],
                },
            )
        )
    return tuple(entities)


def _incident_entities() -> tuple[EntityExpectation, ...]:
    entities = []
    for i in range(1, RECORD_COUNT + 1):
        record = incident_response(i)
        entities.append(
            EntityExpectation(
                identifier=sys_id("incident", i),
                title=record["short_description"],
                properties={
                    "number": record["number"],
                    "state": record["state"],
                    "category": record["category"],
                    "reopenCount": record["reopen_count"],
                    "severity": record["severity"],
                    "assignedTo": record["assigned_to"]["link"],
                    "urgency": record["urgency"],
                    "contactType": record["contact_type"],
                    "createdOn": created_on_iso(i),
                    "createdBy": record["sys_created_by"],
                    "isActive": record["active"],
                    "priority": record["priority"],
                },
            )
        )
    return tuple(entities)


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "sys_user_group": KindExpectation(
        count=RECORD_COUNT, entities=_group_entities()
    ),
    "sc_catalog": KindExpectation(
        count=RECORD_COUNT, entities=_catalog_entities()
    ),
    "incident": KindExpectation(
        count=RECORD_COUNT, entities=_incident_entities()
    ),
}
