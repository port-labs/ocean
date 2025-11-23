from integrations.harbor.mappers import (
    map_artifact,
    map_project,
    map_repository,
    map_user,
)


def test_map_project_combines_members_from_membership() -> None:
    raw_project = {
        "project_name": "alpha",
        "display_name": "Alpha",
        "public": True,
        "visibility": "public",
        "repository_count": 4,
        "owner": "platform",
        "members": ["alice"],
        "member_roles": [{"username": "alice", "role": "Maintainer"}],
    }
    membership = {
        "usernames": ["bob"],
        "members": [{"username": "bob", "role": "Developer"}],
    }

    project = map_project(raw_project, membership)

    assert project.as_dict()["members"] == ["alice", "bob"]
    assert {role["username"] for role in project.as_dict()["member_roles"]} == {
        "alice",
        "bob",
    }


def test_map_repository_derives_name_from_path() -> None:
    raw_repository = {
        "project_name": "alpha",
        "repository_path": "alpha/library/nginx",
        "artifact_count": "5",
        "pull_count": None,
        "creation_time": "2024-01-01T00:00:00Z",
    }

    repository = map_repository(raw_repository)

    assert repository.as_dict()["repository_name"] == "library/nginx"
    assert repository.as_dict()["artifact_count"] == 5
    assert repository.as_dict()["pull_count"] == 0


def test_map_artifact_normalises_labels_and_defaults() -> None:
    raw_artifact = {
        "project_name": "alpha",
        "repository": "library/nginx",
        "repository_path": "alpha/library/nginx",
        "digest": "sha256:123",
        "artifact_type": "IMAGE",
        "media_type": None,
        "tag_count": 2,
        "primary_tag": "latest",
        "labels": ["team:platform"],
        "created_at": "2024-01-01T00:00:00Z",
        "pushed_at": "2024-01-02T00:00:00Z",
        "vulnerability_severity": "High",
        "critical_vulnerability_count": 1,
        "high_vulnerability_count": 2,
        "medium_vulnerability_count": 0,
        "low_vulnerability_count": 0,
        "negligible_vulnerability_count": 0,
        "scan_completed_at": "2024-01-03T00:00:00Z",
    }

    artifact = map_artifact(raw_artifact)

    assert artifact.as_dict()["labels"] == ["team:platform"]
    assert artifact.as_dict()["vulnerability_severity"] == "High"


def test_map_user_defaults_display_name() -> None:
    raw_user = {
        "username": "robot$sync",
        "display_name": None,
        "email": None,
        "creation_time": None,
        "update_time": None,
        "is_robot": True,
        "is_admin": False,
        "projects": ["alpha"],
        "project_roles": [{"project": "alpha", "role": "Maintainer"}],
        "role_names": ["Maintainer"],
    }

    user = map_user(raw_user)

    assert user.as_dict()["display_name"] == "robot$sync"
