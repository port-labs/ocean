from unittest.mock import AsyncMock, MagicMock

import pytest

from azure_integration.foundry.clients.http.foundry_client import FoundryApiError
from azure_integration.foundry.core.exporters.agents_exporter import AgentsExporter
from azure_integration.foundry.core.exporters.model_deployments_exporter import (
    ModelDeploymentsExporter,
)
from azure_integration.foundry.core.exporters.responses_exporter import (
    ResponsesExporter,
)
from azure_integration.foundry.core.options import (
    EndpointScope,
    SingleAgentOptions,
    SingleModelDeploymentOptions,
    SingleResponseOptions,
)

_PROJECT = "https://example.services.ai.azure.com/api/projects/demo"
_PROJECT_ID = "/subscriptions/s/rg/acct/projects/demo"


def _client(payload: object) -> MagicMock:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep.rstrip('/')}/{path}"
    client.send_api_request = AsyncMock(return_value=payload)
    return client


def _not_found_client() -> MagicMock:
    client = MagicMock()
    client.build_url.side_effect = lambda ep, path: f"{ep.rstrip('/')}/{path}"
    client.send_api_request = AsyncMock(
        side_effect=FoundryApiError("not found", status_code=404)
    )
    return client


@pytest.mark.asyncio
async def test_model_deployment_get_resource() -> None:
    client = _client({"name": "gpt-4o", "capabilities": {"chat_completion": "true"}})
    got = await ModelDeploymentsExporter(client).get_resource(
        SingleModelDeploymentOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            deployment_name="gpt-4o",
        )
    )
    assert got is not None and got["name"] == "gpt-4o"
    client.send_api_request.assert_awaited_once()
    assert client.send_api_request.await_args.args[0].endswith("deployments/gpt-4o")

    missing = await ModelDeploymentsExporter(_not_found_client()).get_resource(
        SingleModelDeploymentOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            deployment_name="missing",
        )
    )
    assert missing is None


@pytest.mark.asyncio
async def test_agent_get_resource() -> None:
    client = _client({"id": "agent-1", "definition": {"kind": "prompt"}})
    got = await AgentsExporter(client).get_resource(
        SingleAgentOptions(
            project_endpoint=_PROJECT, project_id=_PROJECT_ID, agent_id="agent-1"
        )
    )
    assert got is not None and got["id"] == "agent-1"
    assert client.send_api_request.await_args.args[0].endswith("agents/agent-1")

    assert (
        await AgentsExporter(_not_found_client()).get_resource(
            SingleAgentOptions(
                project_endpoint=_PROJECT, project_id=_PROJECT_ID, agent_id="missing"
            )
        )
        is None
    )


@pytest.mark.asyncio
async def test_response_get_resource_agent_scope() -> None:
    client = _client({"id": "resp_1", "status": "completed"})
    got = await ResponsesExporter(client).get_resource(
        SingleResponseOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            resource_id="resp_1",
            agent_id="agent-1",
        )
    )
    assert got == {"id": "resp_1", "status": "completed"}
    assert client.send_api_request.await_args.args[0].endswith(
        "agents/agent-1/endpoint/protocols/openai/responses/resp_1"
    )


@pytest.mark.asyncio
async def test_response_get_resource_project_scope() -> None:
    client = _client({"id": "resp_2", "status": "completed"})
    got = await ResponsesExporter(client).get_resource(
        SingleResponseOptions(
            project_endpoint=_PROJECT,
            project_id=_PROJECT_ID,
            resource_id="resp_2",
            endpoint_scope=EndpointScope.PROJECT,
        )
    )
    assert got == {"id": "resp_2", "status": "completed"}
    assert client.send_api_request.await_args.args[0].endswith(
        "openai/v1/responses/resp_2"
    )
    assert (
        await ResponsesExporter(_not_found_client()).get_resource(
            SingleResponseOptions(
                project_endpoint=_PROJECT,
                project_id=_PROJECT_ID,
                resource_id="missing",
                endpoint_scope=EndpointScope.PROJECT,
            )
        )
        is None
    )
