from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from botocore.exceptions import ClientError
from aws.core.exporters.codedeploy.deployment.exporter import (
    CodeDeployDeploymentExporter,
)
from aws.core.exporters.codedeploy.deployment.models import (
    SingleCodeDeployDeploymentRequest,
    PaginatedCodeDeployDeploymentRequest,
)

patch_prefix = "aws.core.exporters.codedeploy.deployment.exporter."


@pytest.fixture
def exporter() -> CodeDeployDeploymentExporter:
    """Create a CodeDeployDeploymentExporter instance for testing."""
    return CodeDeployDeploymentExporter(AsyncMock())


@pytest.fixture
def single_deployment_options() -> SingleCodeDeployDeploymentRequest:
    return SingleCodeDeployDeploymentRequest(
        region="us-east-1",
        account_id="123456789012",
        deployment_id="d-ABC123",
        include=[],
    )


@pytest.fixture
def paginated_deployment_options() -> PaginatedCodeDeployDeploymentRequest:
    return PaginatedCodeDeployDeploymentRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentExporter,
    single_deployment_options: SingleCodeDeployDeploymentRequest,
) -> None:
    # Arrange
    mock_client = AsyncMock()
    mock_client.get_deployment = AsyncMock(
        return_value={
            "deploymentInfo": {"deploymentId": single_deployment_options.deployment_id}
        }
    )
    mock_proxy = AsyncMock()
    mock_proxy.client = mock_client
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector
    mock_inspector.inspect.return_value = [MagicMock()]

    # Act
    result = await exporter.get_resource(single_deployment_options)

    # Assert
    assert result == mock_inspector.inspect.return_value[0]
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_deployment_options.region, "codedeploy"
    )
    mock_client.get_deployment.assert_called_once_with(
        deploymentId=single_deployment_options.deployment_id
    )
    mock_inspector.inspect.assert_called_once_with(
        [single_deployment_options.deployment_id],
        single_deployment_options.include,
        extra_context={
            "AccountId": single_deployment_options.account_id,
            "Region": single_deployment_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_resource_raises_when_deployment_not_found(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentExporter,
    single_deployment_options: SingleCodeDeployDeploymentRequest,
) -> None:
    # Arrange
    mock_client = AsyncMock()
    mock_client.get_deployment = AsyncMock(return_value={})
    mock_proxy = AsyncMock()
    mock_proxy.client = mock_client
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    # Act
    with pytest.raises(ClientError) as error:
        await exporter.get_resource(single_deployment_options)

    # Assert
    assert error.value.response["Error"]["Code"] == "DeploymentDoesNotExistException"
    mock_inspector_class.return_value.inspect.assert_not_called()


@pytest.mark.asyncio
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentExporter,
    paginated_deployment_options: PaginatedCodeDeployDeploymentRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield ["d-1", "d-2"]
            yield ["d-3"]

    mock_proxy.get_paginator = MagicMock(return_value=MockPaginator())

    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector

    first_instance = MagicMock()
    second_instance = MagicMock()
    third_instance = MagicMock()
    mock_inspector.inspect.side_effect = [
        [first_instance, second_instance],
        [third_instance],
    ]

    # Act
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_deployment_options):
        collected.append(page)

    # Assert
    assert collected == [
        [first_instance, second_instance],
        [third_instance],
    ]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_deployment_options.region, "codedeploy"
    )
    mock_proxy.get_paginator.assert_called_once_with("list_deployments", "deployments")
    mock_inspector.inspect.assert_has_calls(
        [
            call(
                ["d-1", "d-2"],
                paginated_deployment_options.include,
                extra_context={
                    "AccountId": paginated_deployment_options.account_id,
                    "Region": paginated_deployment_options.region,
                },
            ),
            call(
                ["d-3"],
                paginated_deployment_options.include,
                extra_context={
                    "AccountId": paginated_deployment_options.account_id,
                    "Region": paginated_deployment_options.region,
                },
            ),
        ]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_paginated_resources_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentExporter,
    paginated_deployment_options: PaginatedCodeDeployDeploymentRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield []

    paginator_instance = MockPaginator()
    mock_proxy.get_paginator = MagicMock(return_value=paginator_instance)

    # Act
    results: list[dict[str, Any]] = []
    async for page in exporter.get_paginated_resources(paginated_deployment_options):
        results.extend(page)

    # Assert
    assert results == []
    mock_proxy.get_paginator.assert_called_once_with("list_deployments", "deployments")
    mock_inspector_class.return_value.inspect.assert_not_called()
