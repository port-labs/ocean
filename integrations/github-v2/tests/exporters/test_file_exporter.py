import pytest
from .conftest import FakeResponse


@pytest.mark.asyncio
async def test_file_exporter_handles_dir_and_404(monkeypatch):
    from github.exporters.file import FileExporter
    from github.exporters.base import BaseExporter

    async def fake_get(_self, url: str, params=None):
        if url == "/repos/acme/missing/contents":
            return FakeResponse(404, payload=None)
        assert url == "/repos/acme/good/contents"
        payload = [
            {"type": "file", "name": "README.md", "path": "README.md", "sha": "x"},
            {"type": "dir", "name": "docs", "path": "docs"},
        ]
        return FakeResponse(200, payload=payload)

    monkeypatch.setattr(BaseExporter, "get_repo_owner", lambda _self: "acme")

    class _Client:
        async def get(self, url: str, params=None):
            return await fake_get(self, url, params)

    fe = FileExporter(repos=["good", "missing"], path="")
    monkeypatch.setattr(fe, "client", _Client())

    files = await fe.export()
    assert len(files) == 1
    assert files[0]["name"] == "README.md"
    assert files[0]["repository"]["name"] == "good"


