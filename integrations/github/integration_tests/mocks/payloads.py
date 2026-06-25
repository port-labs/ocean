from typing import Any

ORG_LOGIN = "port-labs-testing"
ORG_ID = 187526413
INSTALLATION_ID = 101062864
REPO_NAMES = ["test-repo-1", "test-repo-2"]


def org_response() -> dict[str, Any]:
    return {
        "login": ORG_LOGIN,
        "id": ORG_ID,
        "node_id": "O_test",
        "url": f"https://api.github.com/users/{ORG_LOGIN}",
        "repos_url": f"https://api.github.com/users/{ORG_LOGIN}/repos",
        "events_url": f"https://api.github.com/users/{ORG_LOGIN}/events",
        "hooks_url": f"https://api.github.com/users/{ORG_LOGIN}/hooks",
        "issues_url": f"https://api.github.com/users/{ORG_LOGIN}/issues",
        "members_url": f"https://api.github.com/users/{ORG_LOGIN}/members",
        "public_members_url": f"https://api.github.com/users/{ORG_LOGIN}/public_members",
        "avatar_url": f"https://avatars.githubusercontent.com/u/{ORG_ID}",
        "description": "Test organization",
        "type": "Organization",
    }


def repo_response(name: str, idx: int) -> dict[str, Any]:
    return {
        "id": 1000 + idx,
        "node_id": f"R_{name}",
        "name": name,
        "full_name": f"{ORG_LOGIN}/{name}",
        "private": False,
        "owner": {"login": ORG_LOGIN, "id": ORG_ID, "type": "Organization"},
        "html_url": f"https://github.com/{ORG_LOGIN}/{name}",
        "description": f"Test repository {name}",
        "default_branch": "main",
        "language": "Python",
    }


def issue_response(repo_name: str, issue_number: int) -> dict[str, Any]:
    return {
        "id": 2000 + issue_number,
        "number": issue_number,
        "title": f"Issue in {repo_name}",
        "state": "open",
        "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/issues/{issue_number}",
    }


def release_response(repo_name: str, release_id: int) -> dict[str, Any]:
    tag = f"v1.{release_id}.0"
    return {
        "id": 3000 + release_id,
        "tag_name": tag,
        "name": f"Release {release_id} for {repo_name}",
        "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/releases/tag/{tag}",
        "draft": False,
        "prerelease": False,
    }


def tag_response(repo_name: str, tag_id: int) -> dict[str, Any]:
    name = f"v1.{tag_id}.0"
    return {
        "name": name,
        "commit": {
            "sha": f"sha{tag_id}",
            "url": f"https://api.github.com/repos/{ORG_LOGIN}/{repo_name}/git/commits/sha{tag_id}",
        },
    }


def environment_list_response(repo_name: str, env_id: int) -> dict[str, Any]:
    return {
        "total_count": 1,
        "environments": [
            {
                "id": 4000 + env_id,
                "name": f"production-{env_id}",
                "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/settings/environments/production-{env_id}",
            }
        ],
    }


def workflow_list_response(repo_name: str, workflow_id: int) -> dict[str, Any]:
    return {
        "total_count": 1,
        "workflows": [
            {
                "id": workflow_id_for_index(workflow_id),
                "name": f"CI {workflow_id}",
                "path": ".github/workflows/ci.yml",
                "state": "active",
                "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/actions/workflows/ci.yml",
            }
        ],
    }


def branch_response(repo_name: str, branch_id: int) -> dict[str, Any]:
    return [
        {
            "name": "main",
            "commit": {
                "sha": f"branch-sha-{branch_id}",
                "url": f"https://api.github.com/repos/{ORG_LOGIN}/{repo_name}/commits/branch-sha-{branch_id}",
            },
            "protected": False,
        }
    ]


def dependabot_alert_response(repo_name: str, alert_id: int) -> dict[str, Any]:
    return [
        {
            "number": alert_id,
            "state": "open",
            "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/security/dependabot/{alert_id}",
            "security_advisory": {"summary": f"Dependabot alert {alert_id}"},
        }
    ]


def code_scanning_alert_response(repo_name: str, alert_id: int) -> dict[str, Any]:
    return [
        {
            "number": alert_id,
            "state": "open",
            "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/security/code-scanning/{alert_id}",
            "rule": {"description": f"Code scanning alert {alert_id}"},
        }
    ]


def secret_scanning_alert_response(repo_name: str, alert_id: int) -> dict[str, Any]:
    return [
        {
            "number": alert_id,
            "state": "open",
            "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/security/secret-scanning/{alert_id}",
            "secret_type": "custom_pattern",
        }
    ]


def deployment_response(repo_name: str, deployment_id: int) -> dict[str, Any]:
    return [
        {
            "id": deployment_id_for_index(deployment_id),
            "task": "deploy",
            "environment": "production",
            "ref": "main",
            "sha": f"deploy-sha-{deployment_id}",
            "description": f"Deployment {deployment_id} for {repo_name}",
        }
    ]


def deployment_id_for_index(repo_index: int) -> int:
    return 6000 + repo_index


def workflow_id_for_index(repo_index: int) -> int:
    return 5000 + repo_index


def deployment_status_response(repo_name: str, status_id: int) -> list[dict[str, Any]]:
    return [
        {
            "id": 8000 + status_id,
            "state": "success",
            "description": f"Deployment status {status_id} for {repo_name}",
            "environment": "production",
        }
    ]


def workflow_run_list_response(repo_name: str, run_id: int) -> dict[str, Any]:
    run_pk = 9000 + run_id
    return {
        "total_count": 1,
        "workflow_runs": [
            {
                "id": run_pk,
                "name": f"CI run {run_id} for {repo_name}",
                "status": "completed",
                "conclusion": "success",
                "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/actions/runs/{run_pk}",
            }
        ],
    }


def collaborator_response(repo_name: str, collab_id: int) -> dict[str, Any]:
    return [
        {
            "login": f"user-{collab_id}",
            "id": 7000 + collab_id,
            "type": "User",
            "html_url": f"https://github.com/user-{collab_id}",
        }
    ]
