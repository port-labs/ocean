import pytest
import importlib
from port_ocean.context.ocean import ocean as ocean_ctx


def _identity_decorator(*_args, **_kwargs):
    def _wrap(func):
        return func
    return _wrap


@pytest.mark.asyncio
async def test_on_resync_file_uses_loaded_repos_and_exporter(monkeypatch):
    monkeypatch.setattr(ocean_ctx, "on_start", _identity_decorator)
    monkeypatch.setattr(ocean_ctx, "on_resync", _identity_decorator)
    gh_main = importlib.import_module("main")

    async def fake_load_repo_names():
        return ["file_repo"]

    class FakeFileExporter:
        def __init__(self, repos=None, path=""):
            self.repos_received = repos or []
            self.path = path

        async def export(self):
            return [{"name": "README.md", "repository": {"name": self.repos_received[0] if self.repos_received else None}}]

    monkeypatch.setattr(gh_main, "_load_repo_names", fake_load_repo_names)
    monkeypatch.setattr(gh_main, "FileExporter", FakeFileExporter)

    items = await gh_main.on_resync_file("file")
    assert len(items) == 1
    assert items[0]["repository"]["name"] == "file_repo"


