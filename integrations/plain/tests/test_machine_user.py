from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch

import httpx
from port_ocean.context.resource import resource_context
from port_ocean.core.handlers.port_app_config.models import ResourceConfig

from integration import MachineUserResourceConfig
from main import on_resync_machine_users
from plain.queries import LIST_MACHINE_USERS
from tests.kind_helpers import (
    collect_pages,
    exporter_kinds,
    make_client,
    node_selection,
)


def test_list_machine_users_query_contains_fields() -> None:
    selection = node_selection(LIST_MACHINE_USERS)

    assert "id" in selection
    assert "fullName" in selection
    assert "publicName" in selection
    assert "description" in selection
    assert "type" in selection
    assert "isCustomAgent" in selection
    assert "isAssignableToThreads" in selection
    assert "isDeleted" in selection
    assert "hasNextPage" in LIST_MACHINE_USERS
    assert "endCursor" in LIST_MACHINE_USERS


def test_machine_user_kind_is_registered_in_spec() -> None:
    assert "kind: machine-user" in exporter_kinds()


async def test_get_machine_users_yields_mocked_pages() -> None:
    client = make_client()
    seen: dict[str, Any] = {}

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        seen["query"] = query
        seen["operation_name"] = operation_name
        seen["connection_path"] = connection_path
        yield [
            {
                "id": "mu_1",
                "fullName": "Support Bot",
                "isDeleted": False,
            }
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_machine_users())

    assert seen["query"] is LIST_MACHINE_USERS
    assert seen["operation_name"] == "ListMachineUsers"
    assert seen["connection_path"] == "data.machineUsers"
    assert batches[0][0]["id"] == "mu_1"


async def test_get_machine_users_excludes_deleted_when_requested() -> None:
    client = make_client()

    async def paginate_connection(
        query: str,
        operation_name: str,
        variables: dict[str, Any] | None,
        connection_path: str,
    ) -> Any:
        yield [
            {"id": "mu_live", "isDeleted": False},
            {"id": "mu_gone", "isDeleted": True},
        ]

    client.paginate_connection = paginate_connection  # type: ignore[method-assign]
    batches = await collect_pages(client.get_machine_users(exclude_deleted=True))

    assert batches == [[{"id": "mu_live", "isDeleted": False}]]


def _machine_user_resource(exclude_deleted: bool) -> MachineUserResourceConfig:
    config = MachineUserResourceConfig.parse_obj(
        {
            "kind": "machine-user",
            "selector": {
                "query": "true",
                "excludeDeleted": exclude_deleted,
            },
            "port": {
                "entity": {
                    "mappings": {
                        "identifier": ".id",
                        "title": ".fullName",
                        "blueprint": '"plainMachineUser"',
                        "properties": {},
                    }
                }
            },
        }
    )
    assert isinstance(config, MachineUserResourceConfig)
    return config


async def test_resync_machine_users_excludes_deleted_when_flag_is_set() -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_machine_users(self, *, exclude_deleted: bool = False) -> Any:
            seen["exclude_deleted"] = exclude_deleted
            yield [{"id": "mu_1", "isDeleted": False}]

    with patch("main.PlainClient", FakeClient):
        async with resource_context(
            cast(ResourceConfig, _machine_user_resource(True)), 0
        ):
            assert on_resync_machine_users is not None
            batches = await collect_pages(on_resync_machine_users("machine-user"))

    assert seen["exclude_deleted"] is True
    assert batches == [[{"id": "mu_1", "isDeleted": False}]]


async def test_resync_machine_users_includes_deleted_by_default() -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_machine_users(self, *, exclude_deleted: bool = False) -> Any:
            seen["exclude_deleted"] = exclude_deleted
            yield [{"id": "mu_1", "isDeleted": True}]

    with patch("main.PlainClient", FakeClient):
        async with resource_context(
            cast(ResourceConfig, _machine_user_resource(False)), 0
        ):
            assert on_resync_machine_users is not None
            await collect_pages(on_resync_machine_users("machine-user"))

    assert seen["exclude_deleted"] is False


async def test_resync_reads_exclude_flag_without_local_config_class() -> None:
    seen: dict[str, Any] = {}

    class FakeClient:
        def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
            pass

        async def get_machine_users(self, *, exclude_deleted: bool = False) -> Any:
            seen["exclude_deleted"] = exclude_deleted
            yield [{"id": "mu_1"}]

    config = SimpleNamespace(
        kind="machine-user",
        selector=SimpleNamespace(exclude_deleted=True),
    )

    with patch("main.PlainClient", FakeClient):
        async with resource_context(cast(ResourceConfig, config), 0):
            assert on_resync_machine_users is not None
            await collect_pages(on_resync_machine_users("machine-user"))

    assert seen["exclude_deleted"] is True
