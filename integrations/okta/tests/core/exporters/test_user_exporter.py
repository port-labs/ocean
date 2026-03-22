"""Tests for OktaUserExporter."""

import pytest
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, List, cast
from unittest.mock import AsyncMock, Mock

import okta.core.exporters.user_exporter as user_exporter_mod
from okta.core.exporters.user_exporter import OktaUserExporter
from okta.core.options import (
    ListUserOptions,
    GetUserOptions,
)
from okta.clients.http.client import OktaClient


class TestOktaUserExporter:
    """Test cases for OktaUserExporter."""

    @pytest.fixture
    def mock_client(self) -> Any:
        """Create a mock client."""
        return Mock(spec=OktaClient)

    @pytest.fixture
    def exporter(self, mock_client: Any) -> OktaUserExporter:
        """Create a test exporter."""
        return OktaUserExporter(mock_client)

    @pytest.mark.asyncio
    async def test_get_paginated_resources(
        self, exporter: OktaUserExporter, mock_client: Any
    ) -> None:
        """Test getting paginated user resources."""
        mock_users: List[Dict[str, Any]] = [
            {"id": "user1", "profile": {"email": "user1@test.com"}},
            {"id": "user2", "profile": {"email": "user2@test.com"}},
        ]
        mock_groups: List[Dict[str, Any]] = [{"id": "group1", "name": "Group 1"}]

        async def mock_get_users(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if endpoint == "users":
                yield mock_users
            elif "groups" in endpoint:
                yield mock_groups

        object.__setattr__(mock_client, "send_paginated_request", mock_get_users)

        options: ListUserOptions = {"include_groups": True, "fields": "id,profile"}
        users: List[Dict[str, Any]] = []
        async for user_batch in exporter.get_paginated_resources(options):
            users.extend(user_batch)

        assert len(users) == 2
        assert users[0]["id"] == "user1"
        assert users[0]["groups"] == mock_groups

    @pytest.mark.asyncio
    async def test_get_paginated_resources_with_error(
        self, exporter: OktaUserExporter, mock_client: Any
    ) -> None:
        """Test handling errors when enriching user data."""
        mock_users: List[Dict[str, Any]] = [
            {"id": "user1", "profile": {"email": "user1@test.com"}}
        ]

        async def mock_get_users(
            *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield mock_users

        async def mock_get_enrichment(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if endpoint == "users":
                yield mock_users
            else:
                raise Exception("API Error")

        object.__setattr__(mock_client, "send_paginated_request", mock_get_enrichment)

        options: ListUserOptions = {"include_groups": True, "fields": "id,profile"}
        users: List[Dict[str, Any]] = []
        async for user_batch in exporter.get_paginated_resources(options):
            users.extend(user_batch)

        assert len(users) == 1
        assert users[0]["id"] == "user1"
        assert "groups" not in users[0]

    @pytest.mark.asyncio
    async def test_get_resource(self) -> None:
        """Test getting a single user resource."""
        mock_client: OktaClient = Mock(spec=OktaClient)
        exporter = OktaUserExporter(mock_client)

        mock_user = {"id": "user1", "profile": {"email": "user1@example.com"}}
        mock_groups = [{"id": "group1", "name": "Group 1"}]

        cast(Any, mock_client).send_api_request = AsyncMock(return_value=mock_user)

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if "groups" in endpoint:
                yield mock_groups

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated)

        options: GetUserOptions = {"user_id": "user1", "include_groups": True}

        user: Dict[str, Any] = await exporter.get_resource(options)

        assert user["id"] == "user1"
        assert user["groups"] == mock_groups

    @pytest.mark.asyncio
    async def test_fetch_user_groups_paginates_all_pages(self) -> None:
        """Test that _fetch_user_groups collects all pages, not just the first."""
        mock_client: OktaClient = Mock(spec=OktaClient)
        exporter = OktaUserExporter(mock_client)

        page1 = [{"id": f"group{i}"} for i in range(200)]
        page2 = [{"id": f"group{i}"} for i in range(200, 350)]

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield page1
            yield page2

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated)

        groups = await exporter._fetch_user_groups("user1")

        assert len(groups) == 350
        assert groups[0]["id"] == "group0"
        assert groups[199]["id"] == "group199"
        assert groups[200]["id"] == "group200"
        assert groups[349]["id"] == "group349"

    @pytest.mark.asyncio
    async def test_fetch_user_apps_paginates_all_pages(self) -> None:
        """Test that _fetch_user_apps collects all pages, not just the first."""
        mock_client: OktaClient = Mock(spec=OktaClient)
        exporter = OktaUserExporter(mock_client)

        page1 = [{"id": f"app{i}"} for i in range(200)]
        page2 = [{"id": f"app{i}"} for i in range(200, 250)]

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield page1
            yield page2

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated)

        apps = await exporter._fetch_user_apps("user1")

        assert len(apps) == 250

    @pytest.mark.asyncio
    async def test_disk_spill_cleans_up_temp_files(
        self,
        exporter: OktaUserExporter,
        mock_client: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that temp NDJSON files are cleaned up after yielding."""
        monkeypatch.setattr(user_exporter_mod, "SPILL_DIR", str(tmp_path))

        mock_users = [
            {"id": "user1", "profile": {"email": "u1@test.com"}},
        ]

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if endpoint == "users":
                yield mock_users
            elif "groups" in endpoint:
                yield [{"id": "g1"}]

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated)

        options: ListUserOptions = {"include_groups": True, "fields": "id,profile"}
        async for _ in exporter.get_paginated_resources(options):
            pass

        remaining = list(tmp_path.glob("*.ndjson"))
        assert len(remaining) == 0, f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_disk_spill_cleans_up_on_error(
        self,
        exporter: OktaUserExporter,
        mock_client: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that temp files are cleaned up even when enrichment errors occur."""
        monkeypatch.setattr(user_exporter_mod, "SPILL_DIR", str(tmp_path))

        mock_users = [
            {"id": f"user{i}", "profile": {"email": f"u{i}@test.com"}} for i in range(5)
        ]

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if endpoint == "users":
                yield mock_users
            elif "groups" in endpoint:
                raise Exception("API Error")

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated)

        options: ListUserOptions = {"include_groups": True, "fields": "id,profile"}
        async for _ in exporter.get_paginated_resources(options):
            pass

        remaining = list(tmp_path.glob("*.ndjson"))
        assert len(remaining) == 0, f"Temp files not cleaned up: {remaining}"

    @pytest.mark.asyncio
    async def test_disk_spill_sub_batching(
        self,
        exporter: OktaUserExporter,
        mock_client: Any,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Test that disk spill yields correct sub-batch sizes."""
        monkeypatch.setattr(user_exporter_mod, "SPILL_DIR", str(tmp_path))

        mock_users = [
            {"id": f"user{i}", "profile": {"email": f"u{i}@test.com"}}
            for i in range(120)
        ]

        async def mock_paginated(
            endpoint: str, *args: Any, **kwargs: Any
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            if endpoint == "users":
                yield mock_users

        object.__setattr__(mock_client, "send_paginated_request", mock_paginated)

        options: ListUserOptions = {"fields": "id,profile"}
        batches: List[List[Dict[str, Any]]] = []
        async for batch in exporter.get_paginated_resources(options):
            batches.append(batch)

        assert len(batches) == 3
        assert len(batches[0]) == 50
        assert len(batches[1]) == 50
        assert len(batches[2]) == 20

        all_ids = {u["id"] for batch in batches for u in batch}
        assert all_ids == {f"user{i}" for i in range(120)}
