from typing import Any

from mocks.payloads import JIRA_EMAIL, JIRA_HOST, JIRA_TOKEN

_RESOURCES: dict[str, dict[str, Any]] = {
    "project": {
        "kind": "project",
        "selector": {"query": "true"},
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".key",
                    "title": ".name",
                    "blueprint": '"jiraProject"',
                    "properties": {
                        "url": '(.self | split("/") | .[:3] | join("/")) + "/projects/" + .key',
                        "totalIssues": ".insight.totalIssueCount",
                    },
                }
            }
        },
    },
    "issue": {
        "kind": "issue",
        "selector": {
            "query": "true",
            "jql": "project = PORT",
        },
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".key",
                    "title": ".fields.summary",
                    "blueprint": '"jiraIssue"',
                    "properties": {
                        "url": '(.self | split("/") | .[:3] | join("/")) + "/browse/" + .key',
                        "status": ".fields.status.name",
                        "issueType": ".fields.issuetype.name",
                        "creator": ".fields.creator.emailAddress",
                        "priority": ".fields.priority.name",
                        "labels": ".fields.labels",
                        "created": ".fields.created",
                        "updated": ".fields.updated",
                    },
                    "relations": {
                        "project": ".fields.project.key",
                        "assignee": ".fields.assignee.accountId",
                        "reporter": ".fields.reporter.accountId",
                    },
                }
            }
        },
    },
    "user": {
        "kind": "user",
        "selector": {"query": "true"},
        "port": {
            "entity": {
                "mappings": {
                    "identifier": ".accountId",
                    "title": ".displayName",
                    "blueprint": '"jiraUser"',
                    "properties": {
                        "emailAddress": ".emailAddress",
                        "active": ".active",
                        "accountType": ".accountType",
                        "timeZone": ".timeZone",
                        "locale": ".locale",
                        "avatarUrl": '.avatarUrls["48x48"]',
                    },
                }
            }
        },
    },
}


def integration_config() -> dict[str, Any]:
    """Config overrides for the harness — Basic auth (no OAuth HTTP round-trip)."""
    return {
        "integration": {
            "identifier": "test-jira",
            "type": "jira",
            "config": {
                "jira_host": JIRA_HOST,
                "atlassian_user_email": JIRA_EMAIL,
                "atlassian_user_token": JIRA_TOKEN,
            },
        }
    }


def mapping_for_kind(*kinds: str) -> dict[str, Any]:
    """Minimal mapping matching the default port-app-config.yaml for the given kinds."""
    unknown = [kind for kind in kinds if kind not in _RESOURCES]
    if unknown:
        raise ValueError(f"No mapping defined for kind(s): {', '.join(unknown)}")

    return {
        "createMissingRelatedEntities": True,
        "deleteDependentEntities": True,
        "resources": [_RESOURCES[kind] for kind in kinds],
    }
