from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from mocks.graphql_payloads import ORG_MEMBERS
from mocks.payloads import (
    DEFAULT_BRANCH_NAME,
    ORG_LOGIN,
    REPO_NAMES,
    deployment_id_for_index,
    workflow_id_for_index,
)

FieldPath = str | tuple[str | int, ...]


@dataclass(frozen=True)
class RecordExpectation:
    key: dict[str, Any]
    fields: dict[FieldPath, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class KindExpectation:
    count: int
    records: tuple[RecordExpectation, ...]


def _per_repo_pair(
    key_fn: Callable[[int], dict[str, Any]],
    *,
    fields_fn: Callable[[str, int], dict[FieldPath, Any]] | None = None,
) -> tuple[RecordExpectation, ...]:
    return tuple(
        RecordExpectation(
            key={"__repository": repo, **key_fn(index)},
            fields={
                "__organization": ORG_LOGIN,
                **(fields_fn(repo, index) if fields_fn else {}),
            },
        )
        for index, repo in enumerate(REPO_NAMES, start=1)
    )


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "user": KindExpectation(
        count=len(ORG_MEMBERS),
        records=tuple(
            RecordExpectation(
                key={"login": member["login"]},
                fields={"email": member["email"], "name": member["name"]},
            )
            for member in ORG_MEMBERS
        ),
    ),
    "team": KindExpectation(
        count=1,
        records=(
            RecordExpectation(
                key={"slug": "team-alpha"},
                fields={
                    "name": "Team Alpha",
                    "description": "Team Alpha",
                    "__organization": ORG_LOGIN,
                },
            ),
        ),
    ),
    "pull-request-graphql": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda _i: {"number": 1},
            fields_fn=lambda repo, _i: {
                "title": f"Test PR for {repo}",
                "state": "open",
            },
        ),
    ),
    "issue": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"number": i},
            fields_fn=lambda repo, _i: {"title": f"Issue in {repo}", "state": "open"},
        ),
    ),
    "release": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"id": 3000 + i},
            fields_fn=lambda repo, i: {
                "name": f"Release {i} for {repo}",
                "tag_name": f"v1.{i}.0",
            },
        ),
    ),
    "tag": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"name": f"v1.{i}.0"},
            fields_fn=lambda _repo, i: {("commit", "sha"): f"sha{i}"},
        ),
    ),
    "environment": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(lambda i: {"name": f"production-{i}"}),
    ),
    "workflow": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"id": workflow_id_for_index(i)},
            fields_fn=lambda _repo, i: {
                "name": f"CI {i}",
                "path": ".github/workflows/ci.yml",
                "state": "active",
            },
        ),
    ),
    "workflow-run": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"id": 9000 + i},
            fields_fn=lambda repo, i: {
                "name": f"CI run {i} for {repo}",
                "status": "completed",
                "conclusion": "success",
            },
        ),
    ),
    "branch": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda _i: {"name": DEFAULT_BRANCH_NAME},
            fields_fn=lambda _repo, _i: {"protected": False},
        ),
    ),
    "branch-protection": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda _i: {"name": DEFAULT_BRANCH_NAME},
            fields_fn=lambda _repo, _i: {
                "protected": False,
                ("__protection_rules", "required_status_checks", "contexts", 0): "ci",
            },
        ),
    ),
    "branch-detailed": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda _i: {"name": DEFAULT_BRANCH_NAME},
            fields_fn=lambda repo, _i: {
                "protected": False,
                (
                    "commit",
                    "commit",
                    "message",
                ): f"Latest commit on {DEFAULT_BRANCH_NAME} in {repo}",
            },
        ),
    ),
    "dependabot-alert": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"number": i},
            fields_fn=lambda _repo, i: {
                ("security_advisory", "summary"): f"Dependabot alert {i}",
                "state": "open",
            },
        ),
    ),
    "code-scanning-alerts": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"number": i},
            fields_fn=lambda _repo, i: {
                ("rule", "description"): f"Code scanning alert {i}",
                "state": "open",
            },
        ),
    ),
    "secret-scanning-alerts": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"number": i},
            fields_fn=lambda _repo, _i: {
                "secret_type": "custom_pattern",
                "state": "open",
            },
        ),
    ),
    "deployment": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(
            lambda i: {"id": deployment_id_for_index(i)},
            fields_fn=lambda _repo, _i: {
                "task": "deploy",
                "environment": "production",
                "ref": "main",
            },
        ),
    ),
    "deployment-status": KindExpectation(
        count=len(REPO_NAMES),
        records=tuple(
            RecordExpectation(
                key={
                    "__deployment_id": str(deployment_id_for_index(index)),
                    "id": 8000 + index,
                },
                fields={
                    "state": "success",
                    "description": f"Deployment status {index} for {repo}",
                    "environment": "production",
                    "__repository": repo,
                    "__organization": ORG_LOGIN,
                },
            )
            for index, repo in enumerate(REPO_NAMES, start=1)
        ),
    ),
    "collaborator": KindExpectation(
        count=len(REPO_NAMES),
        records=_per_repo_pair(lambda i: {"login": f"user-{i}"}),
    ),
    "package": KindExpectation(
        count=2,
        records=(
            RecordExpectation(
                key={"id": 5001},
                fields={
                    "name": "hello-docker",
                    "visibility": "private",
                    "__repository": "test-repo-1",
                    "__organization": ORG_LOGIN,
                },
            ),
            RecordExpectation(
                key={"id": 5002},
                fields={
                    "name": "api/service",
                    "visibility": "public",
                    "__repository": "test-repo-2",
                    "__organization": ORG_LOGIN,
                },
            ),
        ),
    ),
}
