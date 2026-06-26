from dataclasses import dataclass, field
from typing import Any

from mocks.graphql_payloads import ORG_MEMBERS
from mocks.payloads import (
    DEFAULT_BRANCH_NAME,
    REPO_NAMES,
    deployment_id_for_index,
    workflow_id_for_index,
)


@dataclass(frozen=True)
class EntityExpectation:
    identifier: str
    title: str | None = None
    properties: dict[str, Any] = field(default_factory=dict)
    relations: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class KindExpectation:
    count: int
    entities: tuple[EntityExpectation, ...]


def _repo_entity_id(repo: str, suffix: str) -> str:
    return f"{repo}{suffix}"


def _per_repo_pair(
    suffix_fn,
    *,
    title_fn=None,
    properties_fn=None,
    relations: bool = True,
) -> tuple[EntityExpectation, ...]:
    entities: list[EntityExpectation] = []
    for index, repo in enumerate(REPO_NAMES, start=1):
        suffix = suffix_fn(index)
        entities.append(
            EntityExpectation(
                identifier=_repo_entity_id(repo, suffix),
                title=title_fn(repo, index) if title_fn else None,
                properties=properties_fn(repo, index) if properties_fn else {},
                relations={"repository": repo} if relations else {},
            )
        )
    return tuple(entities)


KIND_EXPECTATIONS: dict[str, KindExpectation] = {
    "user": KindExpectation(
        count=len(ORG_MEMBERS),
        entities=tuple(
            EntityExpectation(
                identifier=member["login"],
                title=member["login"],
                properties={"email": member["email"], "name": member["name"]},
            )
            for member in ORG_MEMBERS
        ),
    ),
    "team": KindExpectation(
        count=1,
        entities=(
            EntityExpectation(
                identifier="team-alpha",
                title="Team Alpha",
                properties={"description": "Team Alpha"},
            ),
        ),
    ),
    "pull-request-graphql": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda _i: "1",
            title_fn=lambda repo, _i: f"Test PR for {repo}",
            properties_fn=lambda _repo, _i: {"status": "open"},
        ),
    ),
    "issue": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(i),
            title_fn=lambda repo, _i: f"Issue in {repo}",
            properties_fn=lambda _repo, _i: {"status": "open"},
        ),
    ),
    "release": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(3000 + i),
            title_fn=lambda repo, i: f"Release {i} for {repo}",
            properties_fn=lambda _repo, i: {"tag": f"v1.{i}.0"},
        ),
    ),
    "tag": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: f"v1.{i}.0",
            title_fn=lambda _repo, i: f"v1.{i}.0",
            properties_fn=lambda _repo, i: {"commitSha": f"sha{i}"},
        ),
    ),
    "environment": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: f"production-{i}",
            title_fn=lambda _repo, i: f"production-{i}",
        ),
    ),
    "workflow": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(workflow_id_for_index(i)),
            title_fn=lambda _repo, i: f"CI {i}",
            properties_fn=lambda _repo, _i: {
                "path": ".github/workflows/ci.yml",
                "state": "active",
            },
        ),
    ),
    "workflow-run": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(9000 + i),
            title_fn=lambda repo, i: f"CI run {i} for {repo}",
            properties_fn=lambda _repo, _i: {
                "status": "completed",
                "conclusion": "success",
            },
        ),
    ),
    "branch": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda _i: DEFAULT_BRANCH_NAME,
            title_fn=lambda _repo, _i: DEFAULT_BRANCH_NAME,
            properties_fn=lambda _repo, _i: {"protected": False},
        ),
    ),
    "branch-protection": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda _i: DEFAULT_BRANCH_NAME,
            title_fn=lambda _repo, _i: DEFAULT_BRANCH_NAME,
            properties_fn=lambda _repo, _i: {
                "protected": False,
                "requiredCheck": "ci",
            },
        ),
    ),
    "branch-detailed": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda _i: DEFAULT_BRANCH_NAME,
            title_fn=lambda _repo, _i: DEFAULT_BRANCH_NAME,
            properties_fn=lambda repo, _i: {
                "protected": False,
                "commitMessage": f"Latest commit on {DEFAULT_BRANCH_NAME} in {repo}",
            },
        ),
    ),
    "dependabot-alert": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(i),
            title_fn=lambda _repo, i: f"Dependabot alert {i}",
            properties_fn=lambda _repo, _i: {"state": "open"},
        ),
    ),
    "code-scanning-alerts": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(i),
            title_fn=lambda _repo, i: f"Code scanning alert {i}",
            properties_fn=lambda _repo, _i: {"state": "open"},
        ),
    ),
    "secret-scanning-alerts": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(i),
            title_fn=lambda _repo, _i: "custom_pattern",
            properties_fn=lambda _repo, _i: {"state": "open"},
        ),
    ),
    "deployment": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: str(deployment_id_for_index(i)),
            title_fn=lambda _repo, _i: "deploy",
            properties_fn=lambda _repo, _i: {
                "environment": "production",
                "ref": "main",
            },
        ),
    ),
    "deployment-status": KindExpectation(
        count=len(REPO_NAMES),
        entities=tuple(
            EntityExpectation(
                identifier=f"{deployment_id_for_index(index)}{8000 + index}",
                title="success",
                properties={
                    "description": f"Deployment status {index} for {repo}",
                    "environment": "production",
                },
                relations={"repository": repo},
            )
            for index, repo in enumerate(REPO_NAMES, start=1)
        ),
    ),
    "collaborator": KindExpectation(
        count=len(REPO_NAMES),
        entities=_per_repo_pair(
            lambda i: f"user-{i}",
            title_fn=lambda _repo, i: f"user-{i}",
        ),
    ),
}
