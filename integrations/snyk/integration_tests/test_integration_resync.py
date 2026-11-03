import os
from typing import Any

import pytest
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)

from expectations import KIND_EXPECTATIONS, assert_raw_items
from mocks.payloads import (
    ORG_ID,
    RECORD_COUNT,
    SNYK_API_URL,
    SNYK_TOKEN,
    org_response,
    project_response,
    target_response,
    vulnerability_response,
)
from mocks.transport_builder import _paginated

_HAPPY_PATH_KINDS = ("organization", "project", "target", "vulnerability")


class TestSnykHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the Snyk integration.

    Exercises a full resync across all four default kinds at once:
    - organization
    - project
    - target
    - vulnerability

    Expected raw items: 1 org, 2 projects, 2 targets, 2 vulnerabilities, each
    checked on the raw fields its Port mapping reads.
    """

    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        t = InterceptTransport(strict=True)

        # Org listing — exact-path callable avoids prefix collision with sub-routes.
        t.add_route(
            "GET",
            lambda r: r.url.path == "/rest/orgs",
            {"status_code": 200, "json": _paginated([org_response()])},
        )
        t.add_route(
            "GET",
            f"/rest/orgs/{ORG_ID}/projects",
            {
                "status_code": 200,
                "json": _paginated(
                    [project_response(i) for i in range(1, RECORD_COUNT + 1)]
                ),
            },
        )
        t.add_route(
            "GET",
            f"/rest/orgs/{ORG_ID}/targets",
            {
                "status_code": 200,
                "json": _paginated(
                    [target_response(i) for i in range(1, RECORD_COUNT + 1)]
                ),
            },
        )
        t.add_route(
            "GET",
            f"/rest/orgs/{ORG_ID}/issues",
            {
                "status_code": 200,
                "json": _paginated(
                    [vulnerability_response(i) for i in range(1, RECORD_COUNT + 1)]
                ),
            },
        )

        return t

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "resources": [
                {
                    "kind": "organization",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".attributes.name",
                                "blueprint": '"snykOrganization"',
                                "properties": {
                                    "slug": ".attributes.slug",
                                    "url": '("https://app.snyk.io/org/" + .attributes.slug | tostring)',
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "project",
                    "selector": {"query": "true", "attachIssuesToProject": False},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".attributes.name",
                                "blueprint": '"snykProject"',
                                "properties": {
                                    "url": '("https://app.snyk.io/org/" + .__organization.slug + "/project/" + .id | tostring)',
                                    "businessCriticality": ".attributes.business_criticality",
                                    "environment": ".attributes.environment",
                                    "lifeCycle": ".attributes.lifecycle",
                                    "highOpenVulnerabilities": ".meta.latest_issue_counts.high",
                                    "mediumOpenVulnerabilities": ".meta.latest_issue_counts.medium",
                                    "lowOpenVulnerabilities": ".meta.latest_issue_counts.low",
                                    "criticalOpenVulnerabilities": ".meta.latest_issue_counts.critical",
                                    "tags": ".attributes.tags",
                                    "targetOrigin": ".attributes.origin",
                                },
                                "relations": {
                                    "snyk_target": ".relationships.target.data.id"
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "target",
                    "selector": {"query": "true", "attachProjectData": False},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".attributes.display_name",
                                "blueprint": '"snykTarget"',
                                "properties": {
                                    "origin": ".relationships.integration.data.attributes.integration_type",
                                },
                                "relations": {
                                    "snyk_organization": ".relationships.organization.data.id"
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "vulnerability",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".attributes.title",
                                "blueprint": '"snykVulnerability"',
                                "properties": {
                                    "score": ".attributes.risk.score.value",
                                    "packageNames": "[.attributes.coordinates[].representations[].dependency?.package_name | select(. != null)]",
                                    "packageVersions": "[.attributes.coordinates[].representations[].dependency?.package_version | select(. != null)]",
                                    "severity": ".attributes.effective_severity_level",
                                    "url": '("https://app.snyk.io/org/" + .__organization.slug + "/project/" + .relationships.scan_item.data.id + "#issue-" + .attributes.key | tostring)',
                                    "publicationTime": ".attributes.created_at",
                                    "status": ".attributes.status",
                                    "type": ".attributes.type",
                                },
                                "relations": {
                                    "project": ".relationships.scan_item.data.id"
                                },
                            }
                        }
                    },
                },
            ]
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-snyk",
                "type": "snyk",
                "config": {
                    "token": SNYK_TOKEN,
                    "api_url": SNYK_API_URL,
                },
            }
        }

    @pytest.mark.asyncio
    async def test_happy_path(self, resync: ResyncResult) -> None:
        assert resync.errors == [], f"Resync had errors: {resync.errors}"
        assert resync.reconciliation_success is True
        assert {batch.kind for batch in resync.raw_batches} == set(_HAPPY_PATH_KINDS)

        for kind in _HAPPY_PATH_KINDS:
            assert_raw_items(resync.raw_items(kind), KIND_EXPECTATIONS[kind], kind)
