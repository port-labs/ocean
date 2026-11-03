from dataclasses import dataclass, field
from typing import Any

from port_ocean.integration_testing import ResyncResult

from mocks.payloads import (
    RECORD_COUNT,
    created_on,
    sys_id,
    incident_response,
    service_catalog_response,
    user_group_response,
)


@dataclass(frozen=True)
class RawExpectation:
    """Expected raw item, located by its natural key.

    `fields` maps dotted raw paths (e.g. ``"assigned_to.link"``) to values.
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


def _group_items() -> tuple[RawExpectation, ...]:
    items = []
    for i in range(1, RECORD_COUNT + 1):
        record = user_group_response(i)
        items.append(
            RawExpectation(
                key=sys_id("group", i),
                fields={
                    "name": record["name"],
                    "description": record["description"],
                    "active": record["active"],
                    "sys_created_on": created_on(i),
                    "sys_created_by": record["sys_created_by"],
                },
            )
        )
    return tuple(items)


def _catalog_items() -> tuple[RawExpectation, ...]:
    items = []
    for i in range(1, RECORD_COUNT + 1):
        record = service_catalog_response(i)
        items.append(
            RawExpectation(
                key=sys_id("catalog", i),
                fields={
                    "title": record["title"],
                    "description": record["description"],
                    "active": record["active"],
                    "sys_created_on": created_on(i),
                    "sys_created_by": record["sys_created_by"],
                },
            )
        )
    return tuple(items)


def _incident_items() -> tuple[RawExpectation, ...]:
    items = []
    for i in range(1, RECORD_COUNT + 1):
        record = incident_response(i)
        items.append(
            RawExpectation(
                key=sys_id("incident", i),
                fields={
                    "short_description": record["short_description"],
                    "number": record["number"],
                    "state": record["state"],
                    "category": record["category"],
                    "reopen_count": record["reopen_count"],
                    "severity": record["severity"],
                    "assigned_to.link": record["assigned_to"]["link"],
                    "urgency": record["urgency"],
                    "contact_type": record["contact_type"],
                    "sys_created_on": created_on(i),
                    "sys_created_by": record["sys_created_by"],
                    "active": record["active"],
                    "priority": record["priority"],
                },
            )
        )
    return tuple(items)


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "sys_user_group": KindExpectation(
        key_field="sys_id", count=RECORD_COUNT, items=_group_items()
    ),
    "sc_catalog": KindExpectation(
        key_field="sys_id", count=RECORD_COUNT, items=_catalog_items()
    ),
    "incident": KindExpectation(
        key_field="sys_id", count=RECORD_COUNT, items=_incident_items()
    ),
}
