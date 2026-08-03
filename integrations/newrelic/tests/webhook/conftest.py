import pytest
from port_ocean.core.handlers.webhook.webhook_event import WebhookEvent

from newrelic_integration.overrides import (
    NewRelicAlertResourceConfig,
    NewRelicCustomResourceConfig,
    NewRelicPortAppConfig,
    NewRelicSelector,
)
from tests.webhook.helpers import port_resource_config


@pytest.fixture
def issue_payload() -> dict[str, object]:
    return {
        "issueId": "issue-1",
        "title": ["High error rate"],
        "state": "ACTIVATED",
        "entityGuids": ["entity-guid-1"],
    }


@pytest.fixture
def webhook_event(issue_payload: dict[str, object]) -> WebhookEvent:
    return WebhookEvent(
        trace_id="test-trace-id",
        payload=issue_payload,
        headers={},
    )


@pytest.fixture
def entity_resource_config() -> NewRelicCustomResourceConfig:
    return NewRelicCustomResourceConfig(
        kind="newRelicService",
        selector=NewRelicSelector(
            query="true",
            newRelicTypes=["APM_APPLICATION"],
            entityQueryFilter="type = 'APM_APPLICATION'",
            calculateOpenIssueCount=True,
        ),
        port=port_resource_config(),
    )


@pytest.fixture
def alert_resource_config() -> NewRelicAlertResourceConfig:
    return NewRelicAlertResourceConfig(
        kind="newRelicAlert",
        selector=NewRelicSelector(query="true"),
        port=port_resource_config(),
    )


@pytest.fixture
def port_app_config(
    alert_resource_config: NewRelicAlertResourceConfig,
    entity_resource_config: NewRelicCustomResourceConfig,
) -> NewRelicPortAppConfig:
    return NewRelicPortAppConfig(
        resources=[alert_resource_config, entity_resource_config]
    )
