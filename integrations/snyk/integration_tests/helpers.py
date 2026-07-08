from typing import Any

from mocks.payloads import SNYK_API_URL, SNYK_TOKEN


def integration_config() -> dict[str, Any]:
    return {
        "integration": {
            "identifier": "test-snyk",
            "type": "snyk",
            "config": {
                "token": SNYK_TOKEN,
                "api_url": SNYK_API_URL,
                # No organization_id/groups → fetches all orgs for the token.
                # No webhook_secret → on_start skips webhook creation.
            },
        }
    }


def mapping_for_kind(kind: str) -> dict[str, Any]:
    resources: dict[str, dict[str, Any]] = {
        "organization": {
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
        "project": {
            "kind": "project",
            "selector": {
                "query": "true",
                # Disable issue attachment to keep transport simple (no issues endpoint).
                "attachIssuesToProject": False,
            },
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
                            "snyk_target": ".relationships.target.data.id",
                        },
                    }
                }
            },
        },
        "target": {
            "kind": "target",
            "selector": {
                "query": "true",
                # Disable project data attachment to keep transport simple.
                "attachProjectData": False,
            },
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
                            "snyk_organization": ".relationships.organization.data.id",
                        },
                    }
                }
            },
        },
        "vulnerability": {
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
                            "project": ".relationships.scan_item.data.id",
                        },
                    }
                }
            },
        },
    }

    if kind not in resources:
        raise ValueError(f"No mapping defined for kind: {kind}")

    return {"resources": [resources[kind]]}
