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


def _repo_scoped_mapping(
    kind: str,
    blueprint: str,
    *,
    identifier: str,
    title: str,
    properties: dict[str, str],
    selector: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "kind": kind,
        "selector": selector or {"query": "true"},
        "port": {
            "entity": {
                "mappings": {
                    "identifier": identifier,
                    "title": title,
                    "blueprint": f'"{blueprint}"',
                    "properties": properties,
                    "relations": {"repository": ".__repository"},
                }
            }
        },
    }


def mapping_for_kind(kind: str) -> dict[str, Any]:
    resources: dict[str, dict[str, Any]] = {
        "issue": _repo_scoped_mapping(
            "issue",
            "githubIssue",
            identifier=".__repository + (.number|tostring)",
            title=".title",
            properties={"status": ".state", "url": ".html_url"},
            selector={"query": "true", "state": "open"},
        ),
        "release": _repo_scoped_mapping(
            "release",
            "githubRelease",
            identifier=".__repository + (.id|tostring)",
            title=".name",
            properties={"tag": ".tag_name", "url": ".html_url"},
        ),
        "tag": _repo_scoped_mapping(
            "tag",
            "githubTag",
            identifier=".__repository + .name",
            title=".name",
            properties={"commitSha": ".commit.sha"},
        ),
        "environment": _repo_scoped_mapping(
            "environment",
            "githubEnvironment",
            identifier=".__repository + .name",
            title=".name",
            properties={"url": ".html_url"},
        ),
        "workflow": _repo_scoped_mapping(
            "workflow",
            "githubWorkflow",
            identifier=".__repository + (.id|tostring)",
            title=".name",
            properties={"path": ".path", "state": ".state"},
        ),
        "branch": _repo_scoped_mapping(
            "branch",
            "githubBranch",
            identifier=".__repository + .name",
            title=".name",
            properties={"protected": ".protected"},
        ),
        "dependabot-alert": _repo_scoped_mapping(
            "dependabot-alert",
            "githubDependabotAlert",
            identifier=".__repository + (.number|tostring)",
            title=".security_advisory.summary",
            properties={"state": ".state", "url": ".html_url"},
        ),
        "code-scanning-alerts": _repo_scoped_mapping(
            "code-scanning-alerts",
            "githubCodeScanningAlert",
            identifier=".__repository + (.number|tostring)",
            title=".rule.description",
            properties={"state": ".state", "url": ".html_url"},
        ),
        "secret-scanning-alerts": _repo_scoped_mapping(
            "secret-scanning-alerts",
            "githubSecretScanningAlert",
            identifier=".__repository + (.number|tostring)",
            title=".secret_type",
            properties={"state": ".state", "url": ".html_url"},
        ),
        "deployment": _repo_scoped_mapping(
            "deployment",
            "githubDeployment",
            identifier=".__repository + (.id|tostring)",
            title=".task",
            properties={"environment": ".environment", "ref": ".ref"},
        ),
        "deployment-status": _repo_scoped_mapping(
            "deployment-status",
            "githubDeploymentStatus",
            identifier=".__deployment_id + (.id|tostring)",
            title=".state",
            properties={
                "description": ".description",
                "environment": ".environment",
            },
        ),
        "workflow-run": _repo_scoped_mapping(
            "workflow-run",
            "githubWorkflowRun",
            identifier=".__repository + (.id|tostring)",
            title=".name",
            properties={
                "status": ".status",
                "conclusion": ".conclusion",
                "url": ".html_url",
            },
        ),
        "collaborator": _repo_scoped_mapping(
            "collaborator",
            "githubCollaborator",
            identifier=".__repository + .login",
            title=".login",
            properties={"url": ".html_url"},
        ),
    }

    if kind not in resources:
        raise ValueError(f"No mapping defined for kind: {kind}")

    return {
        **base_mapping_config(),
        "resources": [resources[kind]],
    }
