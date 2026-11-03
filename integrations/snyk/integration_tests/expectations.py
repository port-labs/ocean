from dataclasses import dataclass, field
from typing import Any

from mocks.payloads import (
    IGNORED_BY_EMAILS,
    IGNORED_BY_NAMES,
    ORG_ID,
    ORG_NAME,
    ORG_SLUG,
    PACKAGE_NAMES,
    PACKAGE_VERSIONS,
    POLICY_IDS,
    PROJECT_IDS,
    RECORD_COUNT,
    TARGET_IDS,
    VULN_IDS,
    VULN_KEYS,
    policy_response,
    project_response,
    vulnerability_response,
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
    records: tuple[RawExpectation, ...]
    key_field: str = "id"


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
    "organization": KindExpectation(
        records=(
            RawExpectation(
                key=ORG_ID,
                fields={
                    "attributes.name": ORG_NAME,
                    "attributes.slug": ORG_SLUG,
                },
            ),
        ),
    ),
    "project": KindExpectation(
        records=tuple(
            RawExpectation(
                key=PROJECT_IDS[i - 1],
                fields={
                    "attributes.name": f"Project {i}",
                    "__organization.id": ORG_ID,
                    "__organization.attributes.slug": ORG_SLUG,
                    "__organization.slug": ORG_SLUG,
                    "attributes.business_criticality": ["high"],
                    "attributes.environment": ["backend"],
                    "attributes.lifecycle": ["production"],
                    "meta.latest_issue_counts": project_response(i)["meta"][
                        "latest_issue_counts"
                    ],
                    "meta.latest_issue_counts.critical": 0,
                    "attributes.tags": [],
                    "attributes.origin": "github",
                    "relationships.target.data.id": TARGET_IDS[i - 1],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "target": KindExpectation(
        records=tuple(
            RawExpectation(
                key=TARGET_IDS[i - 1],
                fields={
                    "attributes.display_name": f"Target {i}",
                    "relationships.integration.data.attributes.integration_type": "github",
                    "relationships.organization.data.id": ORG_ID,
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "vulnerability": KindExpectation(
        records=tuple(
            RawExpectation(
                key=VULN_IDS[i - 1],
                fields={
                    "attributes.title": f"Vulnerability {i}",
                    "attributes.risk.score.value": vulnerability_response(i)[
                        "attributes"
                    ]["risk"]["score"]["value"],
                    "attributes.coordinates": [
                        {
                            "representations": [
                                {
                                    "dependency": {
                                        "package_name": PACKAGE_NAMES[i - 1],
                                        "package_version": PACKAGE_VERSIONS[i - 1],
                                    }
                                }
                            ]
                        }
                    ],
                    "attributes.effective_severity_level": (
                        "high" if i == 1 else "medium"
                    ),
                    "__organization.id": ORG_ID,
                    "__organization.slug": ORG_SLUG,
                    "attributes.key": VULN_KEYS[i - 1],
                    "attributes.created_at": f"2024-01-0{i}T10:00:00Z",
                    "attributes.status": "open",
                    "attributes.type": "package_vulnerability",
                    "relationships.scan_item.data.id": PROJECT_IDS[i - 1],
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "policy": KindExpectation(
        records=tuple(
            RawExpectation(
                key=POLICY_IDS[i - 1],
                fields={
                    "attributes.name": f"Ignore policy {i}",
                    "attributes.ignore_type": policy_response(i)["attributes"][
                        "ignore_type"
                    ],
                    "attributes.ignored_by.name": IGNORED_BY_NAMES[i - 1],
                    "attributes.ignored_by.email": IGNORED_BY_EMAILS[i - 1],
                    "attributes.reason": f"Reason {i}",
                    "relationships.organization.data.id": ORG_ID,
                },
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
}
