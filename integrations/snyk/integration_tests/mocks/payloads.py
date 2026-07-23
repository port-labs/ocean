from typing import Any

SNYK_API_URL = "https://api.snyk.io"
SNYK_TOKEN = "test-snyk-token"

ORG_ID = "org-id-1"
ORG_SLUG = "org-1"
ORG_NAME = "Test Org 1"

RECORD_COUNT = 2

PROJECT_IDS = [f"project-id-{i}" for i in range(1, RECORD_COUNT + 1)]
TARGET_IDS = [f"target-id-{i}" for i in range(1, RECORD_COUNT + 1)]
VULN_IDS = [f"vuln-id-{i}" for i in range(1, RECORD_COUNT + 1)]
VULN_KEYS = [f"SNYK-JS-LODASH-{i}" for i in range(1, RECORD_COUNT + 1)]

PACKAGE_NAMES = ["lodash", "express"]
PACKAGE_VERSIONS = ["4.17.15", "4.17.1"]


def org_response() -> dict[str, Any]:
    return {
        "id": ORG_ID,
        "type": "org",
        "attributes": {
            "name": ORG_NAME,
            "slug": ORG_SLUG,
            "group_id": None,
        },
    }


def project_response(idx: int) -> dict[str, Any]:
    return {
        "id": PROJECT_IDS[idx - 1],
        "type": "project",
        "attributes": {
            "name": f"Project {idx}",
            "business_criticality": ["high"],
            "environment": ["backend"],
            "lifecycle": ["production"],
            "tags": [],
            "origin": "github",
        },
        "meta": {
            "latest_issue_counts": {
                "high": idx,
                "medium": idx * 2,
                "low": idx * 3,
                "critical": 0,
            }
        },
        "relationships": {
            "target": {"data": {"id": TARGET_IDS[idx - 1], "type": "target"}},
            "organization": {"data": {"id": ORG_ID, "type": "org"}},
        },
    }


def target_response(idx: int) -> dict[str, Any]:
    return {
        "id": TARGET_IDS[idx - 1],
        "type": "target",
        "attributes": {
            "display_name": f"Target {idx}",
        },
        "relationships": {
            "organization": {"data": {"id": ORG_ID, "type": "org"}},
            "integration": {
                "data": {
                    "attributes": {"integration_type": "github"},
                }
            },
        },
    }


def vulnerability_response(idx: int) -> dict[str, Any]:
    return {
        "id": VULN_IDS[idx - 1],
        "type": "issue",
        "attributes": {
            "title": f"Vulnerability {idx}",
            "risk": {"score": {"value": 750 - (idx - 1) * 150}},
            "coordinates": [
                {
                    "representations": [
                        {
                            "dependency": {
                                "package_name": PACKAGE_NAMES[idx - 1],
                                "package_version": PACKAGE_VERSIONS[idx - 1],
                            }
                        }
                    ]
                }
            ],
            "effective_severity_level": "high" if idx == 1 else "medium",
            "status": "open",
            "type": "package_vulnerability",
            "created_at": f"2024-01-0{idx}T10:00:00Z",
            "key": VULN_KEYS[idx - 1],
        },
        "relationships": {
            "scan_item": {"data": {"id": PROJECT_IDS[idx - 1], "type": "project"}}
        },
    }
