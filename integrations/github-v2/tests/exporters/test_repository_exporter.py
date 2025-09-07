import pytest
from .conftest import FakeResponse


@pytest.mark.asyncio
async def test_repository_exporter_uses_owner_path(monkeypatch):
    from github.exporters.respository import RepositoryExporter
    from github.exporters.base import BaseExporter

    async def fake_get(_self, url: str, params=None):
        assert url == "/orgs/acme/repos"
        return FakeResponse(200, payload=[{"name": "repo1"}, {"name": "repo2"}])

    monkeypatch.setattr(BaseExporter, "get_base_path", lambda _self: "/orgs/acme")

    class _Client:
        async def get(self, url: str, params=None):
            return await fake_get(self, url, params)

    re = RepositoryExporter()
    monkeypatch.setattr(re, "client", _Client())

    repos = await re.export()
    assert {r["name"] for r in repos} == {"repo1", "repo2"}


