import pytest
from unittest.mock import AsyncMock, patch
from port_ocean.context.ocean import PortOceanContext
from port_ocean.core.handlers.port_app_config.models import (
    EntityMapping,
    MappingsConfig,
    PortResourceConfig,
    ResourceConfig,
)
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent
from webhook_processors.project_webhook_processor import ProjectWebhookProcessor
from webhook_processors.issue_webhook_processor import IssueWebhookProcessor
from webhook_processors.target_webhook_processor import TargetWebhookProcessor
from webhook_processors.vulnerability_webhook_processor import (
    VulnerabilityWebhookProcessor,
)
from typing import Any

from snyk.overrides import (
    ProjectSelector,
    TargetSelector,
    TargetResourceConfig,
    VulnerabilityResourceConfig,
    VulnerabilitySelector,
)


@pytest.fixture
def event() -> WebhookEvent:
    return WebhookEvent(trace_id="test-trace-id", payload={}, headers={})


@pytest.fixture
def projectWebhookProcessor(event: WebhookEvent) -> ProjectWebhookProcessor:
    return ProjectWebhookProcessor(event)


@pytest.fixture
def issueWebhookProcessor(event: WebhookEvent) -> IssueWebhookProcessor:
    return IssueWebhookProcessor(event)


@pytest.fixture
def targetWebhookProcessor(event: WebhookEvent) -> TargetWebhookProcessor:
    return TargetWebhookProcessor(event)


@pytest.fixture
def vulnerabilityWebhookProcessor(event: WebhookEvent) -> VulnerabilityWebhookProcessor:
    return VulnerabilityWebhookProcessor(event)


@pytest.fixture
def resource_config() -> ResourceConfig:
    return ResourceConfig(
        kind="project",
        selector=ProjectSelector(attachIssuesToProject=True, query=""),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".name",
                    blueprint='"service"',
                    properties={
                        "url": ".links.html",
                        "origin": ".origin",
                    },
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def vulnerability_resource_config() -> VulnerabilityResourceConfig:
    return VulnerabilityResourceConfig(
        kind="vulnerability",
        selector=VulnerabilitySelector.parse_obj({"query": "true"}),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".title",
                    blueprint='"snykVulnerability"',
                    properties={},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def target_resource_config() -> TargetResourceConfig:
    return TargetResourceConfig(
        kind="target",
        selector=TargetSelector.parse_obj({"attachProjectData": True, "query": "true"}),
        port=PortResourceConfig(
            entity=MappingsConfig(
                mappings=EntityMapping(
                    identifier=".id",
                    title=".attributes.display_name",
                    blueprint='"snykTarget"',
                    properties={"origin": ".origin"},
                    relations={},
                )
            )
        ),
    )


@pytest.fixture
def mock_context(monkeypatch: Any) -> PortOceanContext:
    mock_context = AsyncMock()
    monkeypatch.setattr(PortOceanContext, "app", mock_context)
    return mock_context


@pytest.mark.asyncio
async def test_shouldProcessEvent_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    with patch("webhook_processors.snyk_base_webhook_processor.hmac") as mock_hmac:
        mock_hmac_obj = mock_hmac.new.return_value
        mock_hmac_obj.hexdigest.return_value = "1234567890"

        mock_request = AsyncMock()
        mock_request.body.return_value = b'{"event":"project.created"}'

        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "event": "project.created",
            },
            headers={"x-hub-signature": "sha256=1234567890"},
        )
        event._original_request = mock_request

        assert await projectWebhookProcessor.should_process_event(event) is True

        mock_hmac_obj.hexdigest.return_value = "1"
        assert await projectWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_shouldProcessEvent_target(
    targetWebhookProcessor: TargetWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    with patch("webhook_processors.snyk_base_webhook_processor.hmac") as mock_hmac:
        mock_hmac_obj = mock_hmac.new.return_value
        mock_hmac_obj.hexdigest.return_value = "1234567890"

        mock_request = AsyncMock()
        mock_request.body.return_value = b'{"event":"project.created"}'

        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={
                "event": "project.created",
            },
            headers={"x-hub-signature": "sha256=1234567890"},
        )
        event._original_request = mock_request
        assert await targetWebhookProcessor.should_process_event(event) is True

        mock_hmac_obj.hexdigest.return_value = "1"
        assert await targetWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_shouldProcessEvent_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await issueWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_getMatchingKinds_projectReturned(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await projectWebhookProcessor.get_matching_kinds(event) == ["project"]


@pytest.mark.asyncio
async def test_getMatchingKinds_issueReturned(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await issueWebhookProcessor.get_matching_kinds(event) == ["issue"]


@pytest.mark.asyncio
async def test_getMatchingKinds_targetReturned(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await targetWebhookProcessor.get_matching_kinds(event) == ["target"]


@pytest.mark.asyncio
async def test_authenticate_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await projectWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    result = await issueWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_authenticate_target(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    result = await targetWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validatePayload_project(
    projectWebhookProcessor: ProjectWebhookProcessor,
) -> None:
    result = await projectWebhookProcessor.validate_payload({"project": {}})
    assert result is True

    result = await projectWebhookProcessor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_validatePayload_issue(
    issueWebhookProcessor: IssueWebhookProcessor,
) -> None:
    result = await issueWebhookProcessor.validate_payload({"project": {}})
    assert result is True

    result = await issueWebhookProcessor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_validatePayload_target(
    targetWebhookProcessor: TargetWebhookProcessor,
) -> None:
    result = await targetWebhookProcessor.validate_payload({"project": {}})
    assert result is True

    result = await targetWebhookProcessor.validate_payload({})
    assert result is False


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_projectReturnedFromClient_updatedRawResultsReturnedCorrectly(
    projectWebhookProcessor: ProjectWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "test-project-id"},
        "org": {"id": "test-org-id"},
    }
    mock_project: dict[str, Any] = {
        "id": "test-project-id",
        "name": "Test Project",
        "origin": "github",
    }

    with patch(
        "webhook_processors.project_webhook_processor.init_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_project(*args: Any, **kwargs: Any) -> dict[str, Any]:
            assert args[0] == "test-org-id"
            assert args[1] == "test-project-id"
            return mock_project

        mock_client.get_single_project = mock_get_project
        mock_create_client.return_value = mock_client

        result = await projectWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_project


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_issuesReturnedFromClient_updatedRawResultsReturnedCorrectly(
    issueWebhookProcessor: IssueWebhookProcessor,
    resource_config: ResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "test-project-id"},
        "org": {"id": "test-org-id"},
    }
    mock_issues: list[dict[str, Any]] = [
        {
            "id": "test-issue-id",
            "title": "Test Issue",
            "severity": "high",
        }
    ]

    with patch(
        "webhook_processors.issue_webhook_processor.init_client"
    ) as mock_create_client:
        mock_client = AsyncMock()

        async def mock_get_issues(*args: Any, **kwargs: Any) -> list[dict[str, Any]]:
            assert args[0] == "test-org-id"
            assert args[1] == "test-project-id"
            return mock_issues

        mock_client.get_issues = mock_get_issues
        mock_create_client.return_value = mock_client

        result = await issueWebhookProcessor.handle_event(payload, resource_config)

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0] == mock_issues[0]


@pytest.mark.asyncio
async def test_handleEvent_projectUpdated_targetReturnedFromClient_updatedRawResultsReturnedCorrectly(
    targetWebhookProcessor: TargetWebhookProcessor,
    target_resource_config: TargetResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "event": "project.updated",
        "project": {"id": "76191494-b77a-422f-8700-1f952136009a"},
        "org": {"id": "047f3b54-6997-402c-80b6-193496030c25"},
    }
    mock_target: dict[str, Any] = {
        "id": "6d3c162a-8951-460d-83b6-96b4478f7e2c",
        "attributes": {"display_name": "production-api-target"},
    }

    with patch("webhook_processors.target_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_org = {"id": "047f3b54-6997-402c-80b6-193496030c25"}
        mock_client.get_all_organizations.return_value = [mock_org]
        mock_client.get_single_target_by_project_id = AsyncMock(
            return_value=mock_target
        )
        mock_init.return_value = mock_client

        await targetWebhookProcessor.handle_event(payload, target_resource_config)

        mock_client.get_single_target_by_project_id.assert_called_once_with(
            mock_org, "76191494-b77a-422f-8700-1f952136009a", attach_project_data=True
        )


@pytest.mark.asyncio
async def test_target_webhook_processor_handle_event_should_return_empty_results_when_org_not_found(
    targetWebhookProcessor: TargetWebhookProcessor,
    target_resource_config: TargetResourceConfig,
) -> None:
    payload = {
        "project": {"id": "76191494-b77a-422f-8700-1f952136009a"},
        "org": {"id": "00000000-0000-0000-0000-000000000000"},
    }

    with patch("webhook_processors.target_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_init.return_value = mock_client
        mock_client.get_all_organizations.return_value = [
            {"id": "047f3b54-6997-402c-80b6-193496030c25"}
        ]

        result = await targetWebhookProcessor.handle_event(
            payload, target_resource_config
        )

        assert result.updated_raw_results == []
        assert result.deleted_raw_results == []


@pytest.mark.asyncio
async def test_target_webhook_processor_handle_event_should_pass_attach_project_data_from_config_to_client(
    targetWebhookProcessor: TargetWebhookProcessor,
    target_resource_config: TargetResourceConfig,
) -> None:
    snyk_org_id = "047f3b54-6997-402c-80b6-193496030c25"
    snyk_project_id = "76191494-b77a-422f-8700-1f952136009a"

    payload = {"project": {"id": snyk_project_id}, "org": {"id": snyk_org_id}}

    with patch("webhook_processors.target_webhook_processor.init_client") as mock_init:
        mock_client = AsyncMock()
        mock_init.return_value = mock_client

        mock_org = {"id": snyk_org_id}
        mock_client.get_all_organizations.return_value = [mock_org]
        mock_client.get_single_target_by_project_id.return_value = {
            "id": "6d3c162a-8951-460d-83b6-96b4478f7e2c"
        }

        await targetWebhookProcessor.handle_event(payload, target_resource_config)

        mock_client.get_single_target_by_project_id.assert_called_once_with(
            mock_org, snyk_project_id, attach_project_data=True
        )


@pytest.mark.asyncio
async def test_getMatchingKinds_vulnerabilityReturned(
    vulnerabilityWebhookProcessor: VulnerabilityWebhookProcessor,
) -> None:
    event = WebhookEvent(trace_id="test-trace-id", payload={}, headers={})
    assert await vulnerabilityWebhookProcessor.get_matching_kinds(event) == [
        "vulnerability"
    ]


@pytest.mark.asyncio
async def test_authenticate_vulnerability(
    vulnerabilityWebhookProcessor: VulnerabilityWebhookProcessor,
) -> None:
    result = await vulnerabilityWebhookProcessor.authenticate({}, {})
    assert result is True


@pytest.mark.asyncio
async def test_validatePayload_vulnerability(
    vulnerabilityWebhookProcessor: VulnerabilityWebhookProcessor,
) -> None:
    assert await vulnerabilityWebhookProcessor.validate_payload({"project": {}}) is True
    assert await vulnerabilityWebhookProcessor.validate_payload({}) is False


@pytest.mark.asyncio
async def test_shouldProcessEvent_vulnerability(
    vulnerabilityWebhookProcessor: VulnerabilityWebhookProcessor,
    mock_context: PortOceanContext,
) -> None:
    with patch("webhook_processors.snyk_base_webhook_processor.hmac") as mock_hmac:
        mock_hmac_obj = mock_hmac.new.return_value
        mock_hmac_obj.hexdigest.return_value = "1234567890"

        mock_request = AsyncMock()
        mock_request.body.return_value = b'{"event":"project.snapshot"}'

        event = WebhookEvent(
            trace_id="test-trace-id",
            payload={"event": "project.snapshot"},
            headers={"x-hub-signature": "sha256=1234567890"},
        )
        event._original_request = mock_request

        assert await vulnerabilityWebhookProcessor.should_process_event(event) is True

        mock_hmac_obj.hexdigest.return_value = "wrong"
        assert await vulnerabilityWebhookProcessor.should_process_event(event) is False


@pytest.mark.asyncio
async def test_handleEvent_vulnerability_issuesEnrichedWithOrg(
    vulnerabilityWebhookProcessor: VulnerabilityWebhookProcessor,
    vulnerability_resource_config: VulnerabilityResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "project": {"id": "test-project-id", "type": "npm"},
        "org": {"id": "test-org-id"},
    }
    mock_org = {"id": "test-org-id", "name": "Test Org"}
    mock_project: dict[str, Any] = {"id": "test-project-id", "type": "npm"}
    mock_issues: list[dict[str, Any]] = [{"id": "vuln-1", "title": "SQL Injection"}]

    async def mock_get_project_vulnerabilities(*args: Any, **kwargs: Any) -> Any:
        yield mock_issues

    with patch(
        "webhook_processors.vulnerability_webhook_processor.init_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_init.return_value = mock_client
        mock_client.get_all_organizations.return_value = [mock_org]
        mock_client.get_single_project.return_value = mock_project
        mock_client.get_project_vulnerabilities = mock_get_project_vulnerabilities

        result = await vulnerabilityWebhookProcessor.handle_event(
            payload, vulnerability_resource_config
        )

        assert len(result.updated_raw_results) == 1
        assert len(result.deleted_raw_results) == 0
        assert result.updated_raw_results[0]["id"] == "vuln-1"
        assert result.updated_raw_results[0]["__organization"] == mock_org


@pytest.mark.asyncio
async def test_handleEvent_vulnerability_no_org_returns_unenriched_issues(
    vulnerabilityWebhookProcessor: VulnerabilityWebhookProcessor,
    vulnerability_resource_config: VulnerabilityResourceConfig,
) -> None:
    payload: dict[str, Any] = {
        "project": {"id": "test-project-id", "type": "npm"},
        "org": {"id": "unknown-org-id"},
    }
    mock_project: dict[str, Any] = {"id": "test-project-id", "type": "npm"}
    mock_issues: list[dict[str, Any]] = [{"id": "vuln-1", "title": "SQL Injection"}]

    async def mock_get_project_vulnerabilities(*args: Any, **kwargs: Any) -> Any:
        yield mock_issues

    with patch(
        "webhook_processors.vulnerability_webhook_processor.init_client"
    ) as mock_init:
        mock_client = AsyncMock()
        mock_init.return_value = mock_client
        mock_client.get_all_organizations.return_value = [{"id": "other-org-id"}]
        mock_client.get_single_project.return_value = mock_project
        mock_client.get_project_vulnerabilities = mock_get_project_vulnerabilities

        result = await vulnerabilityWebhookProcessor.handle_event(
            payload, vulnerability_resource_config
        )

        assert result.updated_raw_results == mock_issues
        assert result.deleted_raw_results == []
