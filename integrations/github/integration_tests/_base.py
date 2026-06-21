"""Shared base for GitHub integration tests.

Provides ``GithubIntegrationTest``: a ``BaseIntegrationTest`` preconfigured
with the happy-path transport, mapping config, and integration config every
GitHub test needs. Individual tests override ``customize_transport`` to add
routes that override the defaults (first-match-wins) and the test function
itself. Nothing more.
"""

import base64
from typing import Any

from port_ocean.integration_testing import BaseIntegrationTest, InterceptTransport


ORG_LOGIN = "port-labs-testing"
ORG_ID = 187526413
INSTALLATION_ID = 101062864
REPO_NAMES = ["test-repo-1", "test-repo-2"]
README_TEXT = "# test readme"


def _org_response() -> dict[str, Any]:
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


def _repo_response(name: str, idx: int) -> dict[str, Any]:
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


def _pull_response(repo_name: str, pr_id: int) -> dict[str, Any]:
    return {
        "id": pr_id,
        "number": pr_id,
        "title": f"Test PR for {repo_name}",
        "state": "open",
        "html_url": f"https://github.com/{ORG_LOGIN}/{repo_name}/pull/{pr_id}",
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-02T00:00:00Z",
        "closed_at": None,
        "merged_at": None,
        "user": {"login": "octocat"},
        "assignees": [],
        "requested_reviewers": [],
        "head": {"repo": {"name": repo_name}},
    }


class GithubIntegrationTest(BaseIntegrationTest):
    def reset_integration_state(self) -> None:
        # Deferred import: the `github` package is only importable once a
        # harness has booted and added the integration path to sys.path. Before
        # the first test there is no stale factory state to clear anyway.
        try:
            from github.clients.client_factory import _reset_clients_after_fork
        except ImportError:
            return
        _reset_clients_after_fork()

    def customize_transport(self, t: InterceptTransport) -> None:
        """Hook for tests that need to override default routes.

        Called BEFORE the default routes are registered, so anything added here
        wins under first-match-wins. Default is a no-op (the happy-path
        transport is used as-is).
        """
        return None

    def create_third_party_transport(self) -> InterceptTransport:
        t = InterceptTransport(strict=False)

        # Test-specific overrides FIRST so they take precedence.
        self.customize_transport(t)

        # GitHub App auth flow
        t.add_route(
            "GET",
            f"/users/{ORG_LOGIN}/installation",
            {
                "status_code": 200,
                "json": {"id": INSTALLATION_ID, "account": _org_response()},
            },
        )
        t.add_route(
            "POST",
            f"/app/installations/{INSTALLATION_ID}/access_tokens",
            {
                "status_code": 201,
                "json": {
                    "token": "ghs_test_token",
                    "expires_at": "2099-12-31T23:59:59Z",
                    "permissions": {"contents": "read", "metadata": "read"},
                    "repository_selection": "all",
                },
            },
        )

        # Organization
        t.add_route(
            "GET",
            f"/users/{ORG_LOGIN}",
            {"status_code": 200, "json": _org_response()},
        )

        # Repositories
        repos = [_repo_response(name, i) for i, name in enumerate(REPO_NAMES)]
        t.add_route(
            "GET",
            f"/orgs/{ORG_LOGIN}/repos",
            {"status_code": 200, "json": repos},
        )

        # Included files: README has content, CODEOWNERS is absent (404)
        encoded_readme = base64.b64encode(README_TEXT.encode()).decode()
        t.add_route(
            "GET",
            r"/repos/port-labs-testing/[^/]+/contents/README\.md",
            {
                "status_code": 200,
                "json": {
                    "name": "README.md",
                    "path": "README.md",
                    "type": "file",
                    "encoding": "base64",
                    "size": len(README_TEXT),
                    "content": encoded_readme,
                },
            },
        )
        t.add_route(
            "GET",
            r"/repos/port-labs-testing/[^/]+/contents/CODEOWNERS",
            {"status_code": 404},
        )

        # Pull requests: one open PR per repo
        for i, name in enumerate(REPO_NAMES, start=1):
            t.add_route(
                "GET",
                f"/repos/{ORG_LOGIN}/{name}/pulls",
                {"status_code": 200, "json": [_pull_response(name, i)]},
            )

        return t

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "repositoryType": "all",
            "resources": [
                {
                    "kind": "organization",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".login",
                                "title": ".login",
                                "blueprint": '"githubOrganization"',
                                "properties": {
                                    "login": ".login",
                                    "id": ".id",
                                    "description": 'if .description then .description else "" end',
                                },
                            }
                        }
                    },
                },
                {
                    "kind": "repository",
                    "selector": {
                        "query": "true",
                        "includedFiles": ["README.md", "CODEOWNERS"],
                    },
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".name",
                                "title": ".name",
                                "blueprint": '"githubRepository"',
                                "properties": {
                                    "description": 'if .description then .description else "" end',
                                    "visibility": 'if .private then "private" else "public" end',
                                    "defaultBranch": ".default_branch",
                                    "readme": '.__includedFiles["README.md"]',
                                    "codeowners": '.__includedFiles["CODEOWNERS"]',
                                    "url": ".html_url",
                                    "language": 'if .language then .language else "" end',
                                },
                                "relations": {"organization": ".owner.login"},
                            }
                        }
                    },
                },
                {
                    "kind": "pull-request",
                    "selector": {"query": "true", "states": ["open"]},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".head.repo.name + (.id|tostring)",
                                "title": ".title",
                                "blueprint": '"githubPullRequest"',
                                "properties": {
                                    "status": ".state",
                                    "createdAt": ".created_at",
                                    "updatedAt": ".updated_at",
                                    "mergedAt": ".merged_at",
                                    "link": ".html_url",
                                    "prNumber": ".id",
                                },
                                "relations": {"repository": ".__repository"},
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
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
