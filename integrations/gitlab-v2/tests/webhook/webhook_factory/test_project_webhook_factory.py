import pytest
from unittest.mock import AsyncMock, MagicMock, call
from typing import Any, cast

from gitlab.webhook.webhook_factory.project_webhook_factory import ProjectWebHook
from gitlab.webhook.events import ProjectEvents

STATIC_WEBHOOK_URL = "https://app.example.com/integration/webhook"


class AsyncIterator:
    """Helper class to properly mock async iterators in tests"""

    def __init__(self, items: list[Any]) -> None:
        self.items = items
        self.index = 0

    def __aiter__(self) -> "AsyncIterator":
        return self

    async def __anext__(self) -> Any:
        if self.index >= len(self.items):
            raise StopAsyncIteration
        value = self.items[self.index]
        self.index += 1
        return value


@pytest.mark.asyncio
class TestProjectWebHook:
    @pytest.fixture
    def client(self) -> Any:
        return MagicMock()

    @pytest.fixture
    def project_webhook(self, client: Any) -> ProjectWebHook:
        return ProjectWebHook(client, "https://app.example.com")

    async def test_webhook_events(self, project_webhook: ProjectWebHook) -> None:
        events = project_webhook.webhook_events()
        assert isinstance(events, ProjectEvents)

    async def test_create_project_webhook_success(
        self, project_webhook: ProjectWebHook, monkeypatch: Any
    ) -> None:
        monkeypatch.setattr(
            project_webhook,
            "create",
            AsyncMock(return_value={"id": 1, "url": STATIC_WEBHOOK_URL}),
        )
        result = await project_webhook.create_project_webhook("123")
        assert result is True
        cast(AsyncMock, project_webhook.create).assert_called_once_with(
            STATIC_WEBHOOK_URL, "projects/123/hooks"
        )

    async def test_create_webhooks_for_personal_projects(
        self, project_webhook: ProjectWebHook, monkeypatch: Any
    ) -> None:
        create_mock = AsyncMock(return_value={"id": 1})
        monkeypatch.setattr(project_webhook, "create", create_mock)

        mock_projects = [
            {"id": 101, "namespace": {"kind": "user"}},
            {"id": 102, "namespace": {"kind": "user"}},
        ]
        monkeypatch.setattr(
            project_webhook._client,
            "get_personal_namespace_projects",
            lambda: AsyncIterator([mock_projects]),
        )

        await project_webhook.create_webhooks_for_personal_projects()

        assert create_mock.call_count == 2
        create_mock.assert_has_calls(
            [
                call(STATIC_WEBHOOK_URL, "projects/101/hooks"),
                call(STATIC_WEBHOOK_URL, "projects/102/hooks"),
            ],
            any_order=True,
        )
