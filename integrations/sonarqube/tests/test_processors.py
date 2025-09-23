import pytest
from unittest.mock import AsyncMock, MagicMock, patch


from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.analysis_webhook_processor import AnalysisWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from integration import (
    ObjectKind,
    SonarQubeGAProjectSelector,
    SonarQubeOnPremAnalysisSelector,
    SonarQubeIssueSelector,
    SonarQubeOnPremAnalysisResourceConfig,
    SonarQubeIssueResourceConfig,
    SonarQubeGAProjectResourceConfig,
)
from typing import Any, AsyncGenerator, Dict, List


from port_ocean.core.handlers.port_app_config.models import (
    ResourceConfig,
    PortResourceConfig,
    MappingsConfig,
    EntityMapping,
    Selector,
)


# Fixtures
@pytest.fixture
async def mock_event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
async def analysis_processor(mock_event: WebhookEvent) -> AnalysisWebhookProcessor:
    return AnalysisWebhookProcessor(mock_event)


@pytest.fixture
async def issue_processor(mock_event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(mock_event)


@pytest.fixture
async def project_processor(mock_event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(mock_event)


@pytest.fixture
async def base_port_config() -> PortResourceConfig:
    return PortResourceConfig(
        entity=MappingsConfig(
            mappings=EntityMapping(
                identifier=".id",
                title=".name",
                blueprint='"project"',
                icon='"SonarQube"',
                properties={},
                relations={},
            )
        )
    )


@pytest.fixture
async def project_resource_config(
    base_port_config: PortResourceConfig,
) -> SonarQubeGAProjectResourceConfig:
    return SonarQubeGAProjectResourceConfig(
        kind="projects_ga",  # Fixed kind value
        selector=SonarQubeGAProjectSelector(  # Fix: Changed to correct selector type
            query="test", metrics=["code_smells", "coverage"]
        ),
        port=base_port_config,
    )


@pytest.fixture
async def on_prem_analysis_resource_config(
    base_port_config: PortResourceConfig,
) -> SonarQubeOnPremAnalysisResourceConfig:
    return SonarQubeOnPremAnalysisResourceConfig(
        kind="onprem_analysis",  # Fixed kind value
        selector=SonarQubeOnPremAnalysisSelector(  # Fix: Changed to correct selector type
            query="test", metrics=["code_smells", "coverage"]
        ),
        port=base_port_config,
    )


@pytest.fixture
async def issue_resource_config(
    base_port_config: PortResourceConfig,
) -> SonarQubeIssueResourceConfig:
    return SonarQubeIssueResourceConfig(
        kind="issues",
        selector=SonarQubeIssueSelector(  # Fix: Changed to correct selector type
            query="test"  # Fix: Removed incorrect parameters
        ),
        port=base_port_config,
    )


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=Selector(query="test"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"project"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def issue_resource_config() -> ResourceConfig:
    # Create a mock selector with the required generate_request_params method
    class MockIssueSelector(Selector):
        def generate_request_params(self) -> dict[str, Any]:
            return {}

    return ResourceConfig(
        kind="issues",
        selector=MockIssueSelector(query="test"),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"issue"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_context(monkeypatch: Any) -> MagicMock:
    mock_context = MagicMock()
    monkeypatch.setattr("port_ocean.context.ocean.ocean", mock_context)
    return mock_context


# Analysis Processor Tests
@pytest.mark.asyncio
async def test_analysis_get_matching_kinds(
    analysis_processor: AnalysisWebhookProcessor,
) -> None:
    dummy_event = WebhookEvent(trace_id="dummy", payload={}, headers={})
    assert await analysis_processor.get_matching_kinds(dummy_event) == [
        ObjectKind.ANALYSIS,
        ObjectKind.SASS_ANALYSIS,
        ObjectKind.ONPREM_ANALYSIS,
    ]


@pytest.mark.asyncio
async def test_analysis_handle_event_cloud(
    analysis_processor: AnalysisWebhookProcessor,
    on_prem_analysis_resource_config: ResourceConfig,
    mock_context: MagicMock,
) -> None:
    mock_context.integration_config = {"sonar_is_on_premise": False}

    with patch(
        "webhook_processors.analysis_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_component.return_value = {"key": "test"}

        async def analysis_generator(
            project: str,
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            yield [{"analysis": "data"}]

        mock_client.get_analysis_by_project = analysis_generator
        mock_init.return_value = mock_client

        result = await analysis_processor.handle_event(
            {"project": "test", "taskId": "123"}, on_prem_analysis_resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {"analysis": "data"}


@pytest.mark.asyncio
async def test_analysis_handle_event_onprem(
    analysis_processor: AnalysisWebhookProcessor,
    resource_config: ResourceConfig,
    mock_context: MagicMock,
) -> None:
    with patch("webhook_processors.analysis_webhook_processor.ocean") as mock_ocean:
        mock_ocean.integration_config = {"sonar_is_on_premise": True}

        with patch(
            "webhook_processors.analysis_webhook_processor.init_sonar_client"
        ) as mock_init:
            mock_client = AsyncMock()
            mock_client.get_single_component.return_value = {"key": "test-project"}

            mock_client.get_measures_for_all_pull_requests.return_value = [
                {"pr": "data"}
            ]
            mock_client.get_analysis_by_project = AsyncMock()
            mock_init.return_value = mock_client

            test_payload = {
                "project": {"key": "test-project-key", "name": "Test Project"},
                "taskId": "analysis123",
                "analysisDate": "2025-01-01",
            }

            result = await analysis_processor.handle_event(
                test_payload, resource_config
            )

            mock_client.get_analysis_by_project.assert_not_called()
            assert len(result.updated_raw_results) == 1
            assert result.updated_raw_results[0] == {"pr": "data"}


@pytest.mark.asyncio
async def test_issue_handle_event(
    issue_processor: IssueWebhookProcessor, issue_resource_config: ResourceConfig
) -> None:
    with patch(
        "webhook_processors.issue_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_component = {"key": "test-project"}
        mock_client.get_single_component.return_value = mock_component

        test_issues = [[{"issue": "1"}, {"issue": "2"}], [{"issue": "3"}]]

        async def mock_issues_generator(
            component: Dict[str, Any], query_params: Dict[str, Any] = {}
        ) -> AsyncGenerator[List[Dict[str, Any]], None]:
            assert component == mock_component
            for batch in test_issues:
                yield batch

        mock_client.get_issues_by_component = mock_issues_generator
        mock_init.return_value = mock_client

        result = await issue_processor.handle_event(
            {"project": "test-project-key"}, issue_resource_config
        )

        mock_client.get_single_component.assert_awaited_once_with("test-project-key")

        expected_issues = []
        async for batch in mock_issues_generator(mock_component, {}):
            expected_issues.extend(batch)

        assert len(result.updated_raw_results) == 3
        assert all(issue in expected_issues for issue in result.updated_raw_results)


# Project Processor Tests
@pytest.mark.asyncio
async def test_project_get_matching_kinds(
    project_processor: ProjectWebhookProcessor,
) -> None:
    dummy_event = WebhookEvent(trace_id="dummy", payload={}, headers={})
    assert await project_processor.get_matching_kinds(dummy_event) == [
        ObjectKind.PROJECTS,
        ObjectKind.PROJECTS_GA,
    ]


@pytest.mark.asyncio
async def test_project_handle_event(
    project_processor: ProjectWebhookProcessor, project_resource_config: ResourceConfig
) -> None:
    with patch(
        "webhook_processors.project_webhook_processor.init_sonar_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_client.get_single_component.return_value = {"key": "test"}
        mock_client.get_single_project.return_value = {"project": "data"}
        mock_init.return_value = mock_client

        result = await project_processor.handle_event(
            {"project": "test"}, project_resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert result.updated_raw_results[0] == {"project": "data"}
