import os
from typing import Any

import pytest
from port_ocean.integration_testing import (
    BaseIntegrationTest,
    InterceptTransport,
    ResyncResult,
)

from mocks.payloads import (
    ORG_ID,
    ORG_NAME,
    ORG_SLUG,
    PACKAGE_NAMES,
    PACKAGE_VERSIONS,
    PROJECT_IDS,
    RECORD_COUNT,
    SNYK_API_URL,
    SNYK_TOKEN,
    TARGET_IDS,
    VULN_IDS,
    VULN_KEYS,
    org_response,
    project_response,
    target_response,
    vulnerability_response,
)
from mocks.transport_builder import _paginated


class TestSnykHappyPath(BaseIntegrationTest):
    """Happy-path integration test for the Snyk integration.

    Exercises a full resync across all four default kinds at once:
    - organization  → snykOrganization entities
    - project       → snykProject entities
    - target        → snykTarget entities
    - vulnerability → snykVulnerability entities

    Expected output: 1 org, 2 projects, 2 targets, 2 vulnerabilities.
    All URL, relation, and property assertions are verified.
    """

    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        t = InterceptTransport(strict=False)

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
                "json": _paginated([project_response(i) for i in range(1, RECORD_COUNT + 1)]),
            },
        )
        t.add_route(
            "GET",
            f"/rest/orgs/{ORG_ID}/targets",
            {
                "status_code": 200,
                "json": _paginated([target_response(i) for i in range(1, RECORD_COUNT + 1)]),
            },
        )
        t.add_route(
            "GET",
            f"/rest/orgs/{ORG_ID}/issues",
            {
                "status_code": 200,
                "json": _paginated([vulnerability_response(i) for i in range(1, RECORD_COUNT + 1)]),
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
                                "relations": {"snyk_target": ".relationships.target.data.id"},
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
                                "relations": {"snyk_organization": ".relationships.organization.data.id"},
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
                                "relations": {"project": ".relationships.scan_item.data.id"},
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

        by_blueprint: dict[str, list[dict[str, Any]]] = {}
        for entity in resync.upserted_entities:
            by_blueprint.setdefault(entity["blueprint"], []).append(entity)

        # --- Organization ---
        orgs = by_blueprint.get("snykOrganization", [])
        assert len(orgs) == 1
        org = orgs[0]
        assert org["identifier"] == ORG_ID
        assert org["title"] == ORG_NAME
        assert org["properties"]["slug"] == ORG_SLUG
        assert org["properties"]["url"] == f"https://app.snyk.io/org/{ORG_SLUG}"

        # --- Projects ---
        projects = by_blueprint.get("snykProject", [])
        assert len(projects) == RECORD_COUNT
        projects_by_id = {e["identifier"]: e for e in projects}
        for i in range(1, RECORD_COUNT + 1):
            project = projects_by_id[PROJECT_IDS[i - 1]]
            assert project["title"] == f"Project {i}"
            props = project["properties"]
            assert props["url"] == f"https://app.snyk.io/org/{ORG_SLUG}/project/{PROJECT_IDS[i - 1]}"
            assert props["targetOrigin"] == "github"
            assert props["highOpenVulnerabilities"] == i
            assert project["relations"]["snyk_target"] == TARGET_IDS[i - 1]

        # --- Targets ---
        targets = by_blueprint.get("snykTarget", [])
        assert len(targets) == RECORD_COUNT
        targets_by_id = {e["identifier"]: e for e in targets}
        for i in range(1, RECORD_COUNT + 1):
            target = targets_by_id[TARGET_IDS[i - 1]]
            assert target["title"] == f"Target {i}"
            assert target["properties"]["origin"] == "github"
            assert target["relations"]["snyk_organization"] == ORG_ID

        # --- Vulnerabilities ---
        vulns = by_blueprint.get("snykVulnerability", [])
        assert len(vulns) == RECORD_COUNT
        vulns_by_id = {e["identifier"]: e for e in vulns}
        for i in range(1, RECORD_COUNT + 1):
            vuln = vulns_by_id[VULN_IDS[i - 1]]
            assert vuln["title"] == f"Vulnerability {i}"
            props = vuln["properties"]
            assert props["packageNames"] == [PACKAGE_NAMES[i - 1]]
            assert props["packageVersions"] == [PACKAGE_VERSIONS[i - 1]]
            assert props["severity"] == ("high" if i == 1 else "medium")
            assert props["status"] == "open"
            assert props["url"] == (
                f"https://app.snyk.io/org/{ORG_SLUG}/project/{PROJECT_IDS[i - 1]}"
                f"#issue-{VULN_KEYS[i - 1]}"
            )
            assert vuln["relations"]["project"] == PROJECT_IDS[i - 1]
