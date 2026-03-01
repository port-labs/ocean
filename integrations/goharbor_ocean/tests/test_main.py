from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from harbor.helpers.utils import ObjectKind
from harbor.webhooks.events import HarborEventType


class TestOnStart:
    @pytest.mark.asyncio
    async def test_on_start_creates_webhooks_for_projects(self):
        from main import on_start

        with patch("main.ocean") as mock_ocean:
            mock_ocean.event_listener_type = "POLLING"
            mock_ocean.app.base_url = "https://test.example.com"
            mock_ocean.integration_config.get.return_value = "test-secret"

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockExporter:
                    mock_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1", "project_id": 1}, {"name": "project2", "project_id": 2}]

                    mock_exporter.get_paginated_resources.return_value = mock_projects()
                    MockExporter.return_value = mock_exporter

                    with patch("main.HarborWebhookClient") as MockWebhookClient:
                        mock_webhook_client = AsyncMock()
                        MockWebhookClient.return_value = mock_webhook_client

                        await on_start()

                        assert mock_webhook_client.upsert_webhook.call_count == 2

                        first_call = mock_webhook_client.upsert_webhook.call_args_list[0]
                        assert first_call[0][0] == "project1"
                        assert first_call[0][1] == "https://test.example.com/webhook"
                        assert HarborEventType.PUSH_ARTIFACT in first_call[0][2]
                        assert HarborEventType.DELETE_ARTIFACT in first_call[0][2]
                        assert HarborEventType.SCANNING_COMPLETED in first_call[0][2]

    @pytest.mark.asyncio
    async def test_on_start_skips_for_once_listener(self):
        from main import on_start

        with patch("main.ocean") as mock_ocean:
            mock_ocean.event_listener_type = "ONCE"

            with patch("main.HarborClientFactory") as mock_factory:
                await on_start()

                mock_factory.get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_start_skips_without_base_url(self):
        from main import on_start

        with patch("main.ocean") as mock_ocean:
            mock_ocean.event_listener_type = "POLLING"
            mock_ocean.app.base_url = None

            with patch("main.HarborClientFactory") as mock_factory:
                await on_start()

                mock_factory.get_client.assert_not_called()

    @pytest.mark.asyncio
    async def test_on_start_skips_without_webhook_secret(self):
        from main import on_start

        with patch("main.ocean") as mock_ocean:
            mock_ocean.event_listener_type = "POLLING"
            mock_ocean.app.base_url = "https://test.com"
            mock_ocean.integration_config.get.return_value = None

            with patch("main.HarborClientFactory") as mock_factory:
                await on_start()

                mock_factory.get_client.assert_not_called()


class TestResyncProjects:
    @pytest.mark.asyncio
    async def test_resync_projects_yields_batches(self):
        from main import resync_projects

        with patch("main.event") as mock_event:
            mock_config = MagicMock()
            mock_config.selector.q = "test-query"
            mock_config.selector.sort = "name"
            mock_event.resource_config = mock_config

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockExporter:
                    mock_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1", "project_id": 1}, {"name": "project2", "project_id": 2}]

                    mock_exporter.get_paginated_resources.return_value = mock_projects()
                    MockExporter.return_value = mock_exporter

                    results = []
                    async for batch in resync_projects(ObjectKind.PROJECT):
                        results.extend(batch)

                    assert len(results) == 2
                    assert results[0]["name"] == "project1"
                    assert results[1]["name"] == "project2"

                    mock_exporter.get_paginated_resources.assert_called_once_with({"q": "test-query", "sort": "name"})


class TestResyncUsers:
    @pytest.mark.asyncio
    async def test_resync_users_yields_batches(self):
        from main import resync_users

        with patch("main.event") as mock_event:
            mock_config = MagicMock()
            mock_config.selector.q = None
            mock_config.selector.sort = "username"
            mock_event.resource_config = mock_config

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborUserExporter") as MockExporter:
                    mock_exporter = AsyncMock()

                    async def mock_users():
                        yield [{"username": "admin", "user_id": 1}, {"username": "developer", "user_id": 2}]

                    mock_exporter.get_paginated_resources.return_value = mock_users()
                    MockExporter.return_value = mock_exporter

                    results = []
                    async for batch in resync_users(ObjectKind.USER):
                        results.extend(batch)

                    assert len(results) == 2
                    assert results[0]["username"] == "admin"
                    assert results[1]["username"] == "developer"


class TestResyncRepositories:
    @pytest.mark.asyncio
    async def test_resync_repositories_iterates_projects(self):
        from main import resync_repositories

        with patch("main.event") as mock_event:
            mock_config = MagicMock()
            mock_config.selector.q = None
            mock_config.selector.sort = None
            mock_event.resource_config = mock_config

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    mock_project_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1"}, {"name": "project2"}]

                    mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                    MockProjectExporter.return_value = mock_project_exporter

                    with patch("main.HarborRepositoryExporter") as MockRepoExporter:
                        mock_repo_exporter = AsyncMock()

                        call_count = 0

                        async def mock_repos_generator():
                            nonlocal call_count
                            call_count += 1
                            if call_count == 1:
                                yield [{"name": "repo1", "project_id": 1}]
                            else:
                                yield [{"name": "repo2", "project_id": 2}]

                        mock_repo_exporter.get_paginated_resources.side_effect = [
                            mock_repos_generator(),
                            mock_repos_generator(),
                        ]
                        MockRepoExporter.return_value = mock_repo_exporter

                        results = []
                        async for batch in resync_repositories(ObjectKind.REPOSITORY):
                            results.extend(batch)

                        assert len(results) == 2
                        assert mock_repo_exporter.get_paginated_resources.call_count == 2


class TestResyncArtifacts:
    @pytest.mark.asyncio
    async def test_resync_artifacts_iterates_projects_and_repos(self):
        from main import resync_artifacts

        with patch("main.event") as mock_event:
            mock_config = MagicMock()
            mock_config.selector.q = None
            mock_config.selector.sort = None
            mock_config.selector.with_tag = True
            mock_config.selector.with_label = True
            mock_config.selector.with_scan_overview = True
            mock_config.selector.with_sbom_overview = False
            mock_config.selector.with_signature = False
            mock_config.selector.with_immutable_status = False
            mock_config.selector.with_accessory = False
            mock_event.resource_config = mock_config

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    mock_project_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1"}]

                    mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                    MockProjectExporter.return_value = mock_project_exporter

                    with patch("main.HarborRepositoryExporter") as MockRepoExporter:
                        mock_repo_exporter = AsyncMock()

                        async def mock_repos():
                            yield [{"name": "repo1"}]

                        mock_repo_exporter.get_paginated_resources.return_value = mock_repos()
                        MockRepoExporter.return_value = mock_repo_exporter

                        with patch("main.HarborArtifactExporter") as MockArtifactExporter:
                            mock_artifact_exporter = AsyncMock()

                            async def mock_artifacts():
                                yield [{"digest": "sha256:abc123", "id": 1}]

                            mock_artifact_exporter.get_paginated_resources.return_value = mock_artifacts()
                            MockArtifactExporter.return_value = mock_artifact_exporter

                            results = []
                            async for batch in resync_artifacts(ObjectKind.ARTIFACT):
                                results.extend(batch)

                            assert len(results) == 1
                            assert results[0]["digest"] == "sha256:abc123"

                            call_args = mock_artifact_exporter.get_paginated_resources.call_args[0][0]
                            assert call_args["project_name"] == "project1"
                            assert call_args["repository_name"] == "repo1"
                            assert call_args["with_tag"] is True
                            assert call_args["with_scan_overview"] is True
                            assert call_args["with_sbom_overview"] is False

    @pytest.mark.asyncio
    async def test_resync_artifacts_with_all_selector_options(self):
        from main import resync_artifacts

        with patch("main.event") as mock_event:
            mock_config = MagicMock()
            mock_config.selector.q = "latest"
            mock_config.selector.sort = "-push_time"
            mock_config.selector.with_tag = True
            mock_config.selector.with_label = True
            mock_config.selector.with_scan_overview = True
            mock_config.selector.with_sbom_overview = True
            mock_config.selector.with_signature = True
            mock_config.selector.with_immutable_status = True
            mock_config.selector.with_accessory = True
            mock_event.resource_config = mock_config

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    mock_project_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "test"}]

                    mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                    MockProjectExporter.return_value = mock_project_exporter

                    with patch("main.HarborRepositoryExporter") as MockRepoExporter:
                        mock_repo_exporter = AsyncMock()

                        async def mock_repos():
                            yield [{"name": "nginx"}]

                        mock_repo_exporter.get_paginated_resources.return_value = mock_repos()
                        MockRepoExporter.return_value = mock_repo_exporter

                        with patch("main.HarborArtifactExporter") as MockArtifactExporter:
                            mock_artifact_exporter = AsyncMock()

                            async def mock_artifacts():
                                yield []

                            mock_artifact_exporter.get_paginated_resources.return_value = mock_artifacts()
                            MockArtifactExporter.return_value = mock_artifact_exporter

                            results = []
                            async for batch in resync_artifacts(ObjectKind.ARTIFACT):
                                results.extend(batch)

                            call_args = mock_artifact_exporter.get_paginated_resources.call_args[0][0]
                            assert call_args["q"] == "latest"
                            assert call_args["sort"] == "-push_time"
                            assert call_args["with_sbom_overview"] is True
                            assert call_args["with_signature"] is True
                            assert call_args["with_immutable_status"] is True
                            assert call_args["with_accessory"] is True
