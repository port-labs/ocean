import pytest
import importlib
from port_ocean.context.ocean import ocean as ocean_ctx


def _identity_decorator(*_args, **_kwargs):
    def _wrap(func):
        return func
    return _wrap


@pytest.mark.asyncio
async def test_on_resync_repository_returns_cached_names(monkeypatch):
    monkeypatch.setattr(ocean_ctx, "on_start", _identity_decorator)
    monkeypatch.setattr(ocean_ctx, "on_resync", _identity_decorator)
    gh_main = importlib.import_module("main")

    gh_main.REPOSITORIES = ["repoA", "repoB"]
    items = await gh_main.on_resync_repository("repository")
    assert items == [{"name": "repoA"}, {"name": "repoB"}]


