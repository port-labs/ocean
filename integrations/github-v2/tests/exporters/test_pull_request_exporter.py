import pytest
from .conftest import FakeResponse


@pytest.mark.asyncio
async def test_pull_request_exporter_sets_repository(monkeypatch):
    from github.exporters.pull_request import PullRequestExporter
    from github.exporters.base import BaseExporter

    async def fake_get(_self, url: str, params=None):
        assert url == "/repos/acme/booklibrary/pulls"
        payload = [{"id": 10, "number": 5, "title": "PR"}]
        return FakeResponse(200, payload=payload)

    monkeypatch.setattr(BaseExporter, "get_repo_owner", lambda _self: "acme")

    class _Client:
        async def get(self, url: str, params=None):
            return await fake_get(self, url, params)

    pe = PullRequestExporter(repos=["booklibrary"])  # pass explicit repositories
    monkeypatch.setattr(pe, "client", _Client())

    prs = await pe.export()
    assert len(prs) == 1
    assert prs[0]["number"] == 5
    assert prs[0]["__repository"] == "booklibrary"


