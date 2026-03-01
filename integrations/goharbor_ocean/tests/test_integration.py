from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from integration import (
    HarborArtifactConfig,
    HarborArtifactSelector,
    HarborProjectConfig,
    HarborProjectSelector,
    HarborRepositoryConfig,
    HarborRepositorySelector,
    HarborUserConfig,
    HarborUserSelector,
)


class TestHarborProjectConfig:
    def test_project_config_with_selector(self):
        selector = HarborProjectSelector(q="test", sort="name")
        config = HarborProjectConfig(kind="project", selector=selector, port={})

        assert config.kind == "project"
        assert config.selector.q == "test"
        assert config.selector.sort == "name"

    def test_project_selector_defaults(self):
        selector = HarborProjectSelector()

        assert selector.q is None
        assert selector.sort is None


class TestHarborUserConfig:
    def test_user_config_with_selector(self):
        selector = HarborUserSelector(q="admin", sort="username")
        config = HarborUserConfig(kind="user", selector=selector, port={})

        assert config.kind == "user"
        assert config.selector.q == "admin"
        assert config.selector.sort == "username"

    def test_user_selector_defaults(self):
        selector = HarborUserSelector()

        assert selector.q is None
        assert selector.sort is None


class TestHarborRepositoryConfig:
    def test_repository_config_with_selector(self):
        selector = HarborRepositorySelector(q="nginx", sort="-name")
        config = HarborRepositoryConfig(kind="repository", selector=selector, port={})

        assert config.kind == "repository"
        assert config.selector.q == "nginx"
        assert config.selector.sort == "-name"

    def test_repository_selector_defaults(self):
        selector = HarborRepositorySelector()

        assert selector.q is None
        assert selector.sort is None


class TestHarborArtifactConfig:
    def test_artifact_config_with_full_selector(self):
        selector = HarborArtifactSelector(
            q="latest",
            sort="-push_time",
            with_tag=True,
            with_label=True,
            with_scan_overview=True,
            with_sbom_overview=True,
            with_signature=True,
            with_immutable_status=True,
            with_accessory=True,
        )
        config = HarborArtifactConfig(kind="artifact", selector=selector, port={})

        assert config.kind == "artifact"
        assert config.selector.q == "latest"
        assert config.selector.sort == "-push_time"
        assert config.selector.with_tag is True
        assert config.selector.with_label is True
        assert config.selector.with_scan_overview is True
        assert config.selector.with_sbom_overview is True
        assert config.selector.with_signature is True
        assert config.selector.with_immutable_status is True
        assert config.selector.with_accessory is True

    def test_artifact_selector_defaults(self):
        selector = HarborArtifactSelector()

        assert selector.q is None
        assert selector.sort is None
        assert selector.with_tag is True
        assert selector.with_label is True
        assert selector.with_scan_overview is True
        assert selector.with_sbom_overview is False
        assert selector.with_signature is False
        assert selector.with_immutable_status is False
        assert selector.with_accessory is False


class TestIntegrationEndToEnd:
    @pytest.mark.asyncio
    async def test_full_resync_flow_all_resources(self):
        from main import (
            resync_artifacts,
            resync_projects,
            resync_repositories,
            resync_users,
        )

        with patch("main.event") as mock_event:
            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                mock_event.resource_config = MagicMock()
                mock_event.resource_config.selector.q = None
                mock_event.resource_config.selector.sort = None
                mock_event.resource_config.selector.with_tag = True
                mock_event.resource_config.selector.with_label = True
                mock_event.resource_config.selector.with_scan_overview = True
                mock_event.resource_config.selector.with_sbom_overview = False
                mock_event.resource_config.selector.with_signature = False
                mock_event.resource_config.selector.with_immutable_status = False
                mock_event.resource_config.selector.with_accessory = False

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    mock_project_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1", "project_id": 1}]

                    mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                    MockProjectExporter.return_value = mock_project_exporter

                    projects = []
                    async for batch in resync_projects("project"):
                        projects.extend(batch)

                    assert len(projects) == 1

                with patch("main.HarborUserExporter") as MockUserExporter:
                    mock_user_exporter = AsyncMock()

                    async def mock_users():
                        yield [{"username": "admin", "user_id": 1}]

                    mock_user_exporter.get_paginated_resources.return_value = mock_users()
                    MockUserExporter.return_value = mock_user_exporter

                    users = []
                    async for batch in resync_users("user"):
                        users.extend(batch)

                    assert len(users) == 1

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    with patch("main.HarborRepositoryExporter") as MockRepoExporter:
                        mock_project_exporter = AsyncMock()

                        async def mock_projects():
                            yield [{"name": "project1"}]

                        mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                        MockProjectExporter.return_value = mock_project_exporter

                        mock_repo_exporter = AsyncMock()

                        async def mock_repos():
                            yield [{"name": "repo1", "id": 1}]

                        mock_repo_exporter.get_paginated_resources.return_value = mock_repos()
                        MockRepoExporter.return_value = mock_repo_exporter

                        repos = []
                        async for batch in resync_repositories("repository"):
                            repos.extend(batch)

                        assert len(repos) == 1

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    with patch("main.HarborRepositoryExporter") as MockRepoExporter:
                        with patch("main.HarborArtifactExporter") as MockArtifactExporter:
                            mock_project_exporter = AsyncMock()

                            async def mock_projects():
                                yield [{"name": "project1"}]

                            mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                            MockProjectExporter.return_value = mock_project_exporter

                            mock_repo_exporter = AsyncMock()

                            async def mock_repos():
                                yield [{"name": "repo1"}]

                            mock_repo_exporter.get_paginated_resources.return_value = mock_repos()
                            MockRepoExporter.return_value = mock_repo_exporter

                            mock_artifact_exporter = AsyncMock()

                            async def mock_artifacts():
                                yield [{"digest": "sha256:abc", "id": 1}]

                            mock_artifact_exporter.get_paginated_resources.return_value = mock_artifacts()
                            MockArtifactExporter.return_value = mock_artifact_exporter

                            artifacts = []
                            async for batch in resync_artifacts("artifact"):
                                artifacts.extend(batch)

                            assert len(artifacts) == 1

    @pytest.mark.asyncio
    async def test_webhook_setup_on_integration_start(self):
        from main import on_start

        with patch("main.ocean") as mock_ocean:
            mock_ocean.event_listener_type = "POLLING"
            mock_ocean.app.base_url = "https://test.com"
            mock_ocean.integration_config.get.return_value = "secret"

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockExporter:
                    mock_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1"}, {"name": "project2"}, {"name": "project3"}]

                    mock_exporter.get_paginated_resources.return_value = mock_projects()
                    MockExporter.return_value = mock_exporter

                    with patch("main.HarborWebhookClient") as MockWebhookClient:
                        mock_webhook_client = AsyncMock()
                        MockWebhookClient.return_value = mock_webhook_client

                        await on_start()

                        assert mock_webhook_client.upsert_webhook.call_count == 3

    @pytest.mark.asyncio
    async def test_resync_handles_empty_results(self):
        from main import resync_projects

        with patch("main.event") as mock_event:
            mock_event.resource_config = MagicMock()
            mock_event.resource_config.selector.q = None
            mock_event.resource_config.selector.sort = None

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockExporter:
                    mock_exporter = AsyncMock()

                    async def mock_empty():
                        yield []

                    mock_exporter.get_paginated_resources.return_value = mock_empty()
                    MockExporter.return_value = mock_exporter

                    results = []
                    async for batch in resync_projects("project"):
                        results.extend(batch)

                    assert len(results) == 0

    @pytest.mark.asyncio
    async def test_resync_handles_multiple_batches(self):
        from main import resync_projects

        with patch("main.event") as mock_event:
            mock_event.resource_config = MagicMock()
            mock_event.resource_config.selector.q = None
            mock_event.resource_config.selector.sort = None

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockExporter:
                    mock_exporter = AsyncMock()

                    async def mock_batches():
                        yield [{"name": "project1"}, {"name": "project2"}]
                        yield [{"name": "project3"}, {"name": "project4"}]
                        yield [{"name": "project5"}]

                    mock_exporter.get_paginated_resources.return_value = mock_batches()
                    MockExporter.return_value = mock_exporter

                    results = []
                    async for batch in resync_projects("project"):
                        results.extend(batch)

                    assert len(results) == 5
                    assert results[0]["name"] == "project1"
                    assert results[4]["name"] == "project5"

    @pytest.mark.asyncio
    async def test_repository_resync_with_multiple_projects(self):
        from main import resync_repositories

        with patch("main.event") as mock_event:
            mock_event.resource_config = MagicMock()
            mock_event.resource_config.selector.q = None
            mock_event.resource_config.selector.sort = None

            with patch("main.HarborClientFactory") as mock_factory:
                mock_client = AsyncMock()
                mock_factory.get_client.return_value = mock_client

                with patch("main.HarborProjectExporter") as MockProjectExporter:
                    mock_project_exporter = AsyncMock()

                    async def mock_projects():
                        yield [{"name": "project1"}, {"name": "project2"}, {"name": "project3"}]

                    mock_project_exporter.get_paginated_resources.return_value = mock_projects()
                    MockProjectExporter.return_value = mock_project_exporter

                    with patch("main.HarborRepositoryExporter") as MockRepoExporter:
                        mock_repo_exporter = AsyncMock()

                        call_number = 0

                        async def mock_repos():
                            nonlocal call_number
                            call_number += 1
                            yield [{"name": f"repo{call_number}"}]

                        mock_repo_exporter.get_paginated_resources.side_effect = [
                            mock_repos(),
                            mock_repos(),
                            mock_repos(),
                        ]
                        MockRepoExporter.return_value = mock_repo_exporter

                        results = []
                        async for batch in resync_repositories("repository"):
                            results.extend(batch)

                        assert len(results) == 3
                        assert mock_repo_exporter.get_paginated_resources.call_count == 3

    @pytest.mark.asyncio
    async def test_artifact_resync_with_nested_iteration(self):
        from main import resync_artifacts

        with patch("main.event") as mock_event:
            mock_event.resource_config = MagicMock()
            mock_event.resource_config.selector.q = None
            mock_event.resource_config.selector.sort = None
            mock_event.resource_config.selector.with_tag = True
            mock_event.resource_config.selector.with_label = False
            mock_event.resource_config.selector.with_scan_overview = False
            mock_event.resource_config.selector.with_sbom_overview = False
            mock_event.resource_config.selector.with_signature = False
            mock_event.resource_config.selector.with_immutable_status = False
            mock_event.resource_config.selector.with_accessory = False

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

                        async def mock_repos_p1():
                            yield [{"name": "repo1"}, {"name": "repo2"}]

                        async def mock_repos_p2():
                            yield [{"name": "repo3"}]

                        mock_repo_exporter.get_paginated_resources.side_effect = [mock_repos_p1(), mock_repos_p2()]
                        MockRepoExporter.return_value = mock_repo_exporter

                        with patch("main.HarborArtifactExporter") as MockArtifactExporter:
                            mock_artifact_exporter = AsyncMock()

                            artifact_call = 0

                            async def mock_artifacts():
                                nonlocal artifact_call
                                artifact_call += 1
                                yield [{"digest": f"sha256:art{artifact_call}"}]

                            mock_artifact_exporter.get_paginated_resources.side_effect = [
                                mock_artifacts(),
                                mock_artifacts(),
                                mock_artifacts(),
                            ]
                            MockArtifactExporter.return_value = mock_artifact_exporter

                            results = []
                            async for batch in resync_artifacts("artifact"):
                                results.extend(batch)

                            assert len(results) == 3
                            assert mock_artifact_exporter.get_paginated_resources.call_count == 3
