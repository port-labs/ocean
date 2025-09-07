import pytest
from .conftest import FakeResponse


@pytest.mark.asyncio
async def test_issue_exporter_filters_prs_and_sets_repository(monkeypatch):
    from github.exporters.issue import IssueExporter
    from github.exporters.base import BaseExporter

    async def fake_get(_self, url: str, params=None):
        assert url == "/repos/acme/booklibrary/issues"
        payload = [
            {"id": 1, "title": "real issue"},
            {"id": 2, "title": "is a pr", "pull_request": {"url": "..."}},
        ]
        return FakeResponse(200, payload=payload)

    monkeypatch.setattr(BaseExporter, "get_repo_owner", lambda _self: "acme")

    class _Client:
        async def get(self, url: str, params=None):
            return await fake_get(self, url, params)

    ie = IssueExporter(repos=["booklibrary"])  # pass explicit repositories
    monkeypatch.setattr(ie, "client", _Client())

    issues = await ie.export()
    assert len(issues) == 1
    assert issues[0]["title"] == "real issue"
    assert issues[0]["__repository"] == "booklibrary"


