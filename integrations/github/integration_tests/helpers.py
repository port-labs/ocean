from typing import Any

from mocks.payloads import ORG_LOGIN


def base_mapping_config() -> dict[str, Any]:
    return {
        "deleteDependentEntities": True,
        "createMissingRelatedEntities": True,
        "repositoryType": "all",
    }


def integration_config() -> dict[str, Any]:
    return {
        "integration": {
            "identifier": "test-github",
            "type": "github",
            "config": {
                "github_host": "https://api.github.com",
                "github_token": "test-value",
                "github_app_id": "12345",
                "github_app_installation_id": "placeholder",
                "github_app_private_key": "test-value",
                "github_organization": ORG_LOGIN,
                "webhook_secret": "test-value",
                "skip_webhook_patching": True,
            },
        }
    }


def mapping_for_kind(kind: str) -> dict[str, Any]:
    resources: dict[str, dict[str, Any]] = {
        "issue": {
            "kind": "issue",
            "selector": {"query": "true", "state": "open"},
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".__repository + (.number|tostring)",
                        "title": ".title",
                        "blueprint": '"githubIssue"',
                        "properties": {
                            "status": ".state",
                            "url": ".html_url",
                        },
                        "relations": {"repository": ".__repository"},
                    }
                }
            },
        },
        "release": {
            "kind": "release",
            "selector": {"query": "true"},
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".__repository + (.id|tostring)",
                        "title": ".name",
                        "blueprint": '"githubRelease"',
                        "properties": {
                            "tag": ".tag_name",
                            "url": ".html_url",
                        },
                        "relations": {"repository": ".__repository"},
                    }
                }
            },
        },
    }

    if kind not in resources:
        raise ValueError(f"No mapping defined for kind: {kind}")

    return {
        **base_mapping_config(),
        "resources": [resources[kind]],
    }
