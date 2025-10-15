from typing import Any, AsyncIterator

import pytest

from integrations.harbor.exporters.users import UsersExporter


class _StubResponse:
    def __init__(self, payload: Any) -> None:
        self._payload = payload

    def json(self) -> Any:
        return self._payload


class _StubHarborClient:
    def __init__(
        self,
        user_pages: list[list[dict[str, Any]]],
        membership_payloads: dict[int, list[dict[str, Any]]],
    ) -> None:
        self.user_pages = user_pages
        self.membership_payloads = membership_payloads

    async def iter_pages(
        self, _path: str, **_kwargs: Any
    ) -> AsyncIterator[list[dict[str, Any]]]:
        for page in self.user_pages:
            yield page

    async def get(self, path: str, **_kwargs: Any) -> _StubResponse:
        project_id = int(path.rsplit("/", 2)[1])
        return _StubResponse(self.membership_payloads.get(project_id, []))


@pytest.mark.asyncio
async def test_users_exporter_enriches_memberships() -> None:
    client = _StubHarborClient(
        user_pages=[
            [
                {
                    "user_id": 10,
                    "username": "alice",
                    "email": "alice@example.com",
                    "realname": "Alice Smith",
                    "has_admin_role": True,
                },
                {
                    "user_id": 11,
                    "username": "robot$port-automation",
                    "email": None,
                },
            ]
        ],
        membership_payloads={
            1: [
                {
                    "entity_type": "u",
                    "role_name": "Developer",
                    "member_user": {"username": "alice", "user_id": 10},
                },
                {
                    "entity_type": "r",
                    "role_name": "Project Admin",
                    "entity_name": "robot$port-automation",
                    "member_user": {"username": "robot$port-automation", "user_id": 11},
                },
            ]
        },
    )

    exporter = UsersExporter(client, project_lookup={1: "alpha"})

    users: list[dict[str, Any]] = []
    async for batch in exporter.iter_users():
        users.extend(batch)

    alice = next(user for user in users if user["username"] == "alice")
    robot = next(user for user in users if user["username"] == "robot$port-automation")

    assert alice["projects"] == ["alpha"]
    assert alice["role_names"] == ["Developer"]
    assert alice["is_admin"] is True
    assert alice["is_robot"] is False

    assert robot["projects"] == ["alpha"]
    assert robot["is_robot"] is True
    assert robot["role_names"] == ["Project Admin"]


@pytest.mark.asyncio
async def test_membership_index_returns_project_mapping() -> None:
    client = _StubHarborClient(
        user_pages=[],
        membership_payloads={
            5: [
                {
                    "entity_type": "u",
                    "role_name": "Maintainer",
                    "member_user": {"username": "bob", "user_id": 77},
                },
                {
                    "entity_type": "g",  # should be ignored
                    "member_user": {"username": "ignored-group"},
                },
            ]
        },
    )

    exporter = UsersExporter(client, project_lookup={5: "platform"})

    user_index, project_index = await exporter.membership_index()

    bob_entry = user_index["user:bob"]
    assert bob_entry["projects"] == ["platform"]
    assert bob_entry["role_names"] == ["Maintainer"]

    project_entry = project_index["platform"]
    assert project_entry["usernames"] == ["bob"]
