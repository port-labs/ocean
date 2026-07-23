from dataclasses import dataclass, field
from typing import Any

from mocks.payloads import (
    ORG_ID,
    ORG_NAME,
    ORG_SLUG,
    PACKAGE_NAMES,
    PACKAGE_VERSIONS,
    PROJECT_IDS,
    RECORD_COUNT,
    TARGET_IDS,
    VULN_IDS,
    VULN_KEYS,
    project_response,
    vulnerability_response,
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


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "organization": KindExpectation(
        count=1,
        entities=(
            EntityExpectation(
                identifier=ORG_ID,
                title=ORG_NAME,
                properties={
                    "slug": ORG_SLUG,
                    "url": f"https://app.snyk.io/org/{ORG_SLUG}",
                },
            ),
        ),
    ),
    "project": KindExpectation(
        count=RECORD_COUNT,
        entities=tuple(
            EntityExpectation(
                identifier=PROJECT_IDS[i - 1],
                title=f"Project {i}",
                properties={
                    "url": f"https://app.snyk.io/org/{ORG_SLUG}/project/{PROJECT_IDS[i - 1]}",
                    "businessCriticality": ["high"],
                    "environment": ["backend"],
                    "lifeCycle": ["production"],
                    "highOpenVulnerabilities": project_response(i)["meta"]["latest_issue_counts"]["high"],
                    "mediumOpenVulnerabilities": project_response(i)["meta"]["latest_issue_counts"]["medium"],
                    "lowOpenVulnerabilities": project_response(i)["meta"]["latest_issue_counts"]["low"],
                    "criticalOpenVulnerabilities": 0,
                    "tags": [],
                    "targetOrigin": "github",
                },
                relations={"snyk_target": TARGET_IDS[i - 1]},
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "target": KindExpectation(
        count=RECORD_COUNT,
        entities=tuple(
            EntityExpectation(
                identifier=TARGET_IDS[i - 1],
                title=f"Target {i}",
                properties={"origin": "github"},
                relations={"snyk_organization": ORG_ID},
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
    "vulnerability": KindExpectation(
        count=RECORD_COUNT,
        entities=tuple(
            EntityExpectation(
                identifier=VULN_IDS[i - 1],
                title=f"Vulnerability {i}",
                properties={
                    "score": vulnerability_response(i)["attributes"]["risk"]["score"]["value"],
                    "packageNames": [PACKAGE_NAMES[i - 1]],
                    "packageVersions": [PACKAGE_VERSIONS[i - 1]],
                    "severity": "high" if i == 1 else "medium",
                    "url": f"https://app.snyk.io/org/{ORG_SLUG}/project/{PROJECT_IDS[i - 1]}#issue-{VULN_KEYS[i - 1]}",
                    "publicationTime": f"2024-01-0{i}T10:00:00Z",
                    "status": "open",
                    "type": "package_vulnerability",
                },
                relations={"project": PROJECT_IDS[i - 1]},
            )
            for i in range(1, RECORD_COUNT + 1)
        ),
    ),
}
