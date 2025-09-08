import pytest
from datetime import datetime, timedelta, timezone


@pytest.mark.asyncio
async def test_pull_request_exporter_uses_state_from_settings(monkeypatch):
    from github.exporters.pull_request import PullRequestExporter
    from github.exporters.base import BaseExporter
    from github.settings import SETTINGS

    # Arrange settings
    monkeypatch.setattr(SETTINGS, "pr_state", "open")
    monkeypatch.setattr(SETTINGS, "pr_updated_since_days", None)

    # Provide a single repo
    monkeypatch.setattr(
        BaseExporter, "get_repo_owner", lambda _self: "acme"
    )

    class _Client:
        def __init__(self):
            self.calls: list[dict] = []

        async def get_paginated(self, url: str, params=None):
            # Assert state propagated
            assert url == "/repos/acme/booklibrary/pulls"
            assert params["state"] == "open"
            return [{"id": 1, "updated_at": "2025-01-01T00:00:00Z"}]

    pe = PullRequestExporter(repos=["booklibrary"])  # explicit repos
    monkeypatch.setattr(pe, "client", _Client())

    # Act
    prs = await pe.export()

    # Assert
    assert len(prs) == 1
    assert prs[0]["__repository"] == "booklibrary"


@pytest.mark.asyncio
async def test_pull_request_exporter_filters_by_updated_since_days(monkeypatch):
    from github.exporters.pull_request import PullRequestExporter
    from github.exporters.base import BaseExporter
    from github.settings import SETTINGS

    # 10 days cutoff
    monkeypatch.setattr(SETTINGS, "pr_state", "all")
    monkeypatch.setattr(SETTINGS, "pr_updated_since_days", "10")

    monkeypatch.setattr(
        BaseExporter, "get_repo_owner", lambda _self: "acme"
    )

    cutoff = datetime.now(timezone.utc) - timedelta(days=10)
    newer = (cutoff + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    older = (cutoff - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

    class _Client:
        async def get_paginated(self, url: str, params=None):
            assert url == "/repos/acme/booklibrary/pulls"
            return [
                {"id": 1, "updated_at": newer},
                {"id": 2, "updated_at": older},
            ]

    pe = PullRequestExporter(repos=["booklibrary"])  # explicit repos
    monkeypatch.setattr(pe, "client", _Client())

    prs = await pe.export()

    # Only the newer PR should remain after filtering
    assert len(prs) == 1
    assert prs[0]["id"] == 1
    assert prs[0]["__repository"] == "booklibrary"


