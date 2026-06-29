from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from aws.core.exporters.codedeploy.deployment_target.exporter import (
    CodeDeployDeploymentTargetExporter,
)
from aws.core.exporters.codedeploy.deployment_target.models import (
    SingleCodeDeployDeploymentTargetRequest,
    PaginatedCodeDeployDeploymentTargetRequest,
)

patch_prefix = "aws.core.exporters.codedeploy.deployment_target.exporter"


@pytest.fixture
def exporter() -> CodeDeployDeploymentTargetExporter:
    """Create a CodeDeployDeploymentTargetExporter instance for testing."""
    return CodeDeployDeploymentTargetExporter(AsyncMock())


@pytest.fixture
def single_deployment_target_options() -> SingleCodeDeployDeploymentTargetRequest:
    return SingleCodeDeployDeploymentTargetRequest(
        region="us-east-1",
        account_id="123456789012",
        deployment_id="d-EXAMPLE11",
        target_id="i-0123456789abcdef0",
        include=[],
    )


@pytest.fixture
def paginated_deployment_target_options() -> PaginatedCodeDeployDeploymentTargetRequest:
    return PaginatedCodeDeployDeploymentTargetRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.DeploymentTargetActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployDeploymentTargetExporter,
    single_deployment_target_options: SingleCodeDeployDeploymentTargetRequest,
) -> None:
    # Arrange
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector
    mock_inspector.inspect.return_value = [MagicMock()]

    # Act
    result = await exporter.get_resource(single_deployment_target_options)

    # Assert
    assert result == mock_inspector.inspect.return_value[0]
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_deployment_target_options.region, "codedeploy"
    )
    mock_input.assert_called_once_with(
        deployment_id=single_deployment_target_options.deployment_id,
        items=[single_deployment_target_options.target_id],
        region=single_deployment_target_options.region,
        account_id=single_deployment_target_options.account_id,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_deployment_target_options.include,
        extra_context={
            "AccountId": single_deployment_target_options.account_id,
            "Region": single_deployment_target_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.DeploymentTargetActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_empty_inspection_returns_empty_dict(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployDeploymentTargetExporter,
    single_deployment_target_options: SingleCodeDeployDeploymentTargetRequest,
) -> None:
    # Arrange
    mock_inspector = AsyncMock()
    mock_inspector.inspect.return_value = []
    mock_inspector_class.return_value = mock_inspector

    # Act
    result = await exporter.get_resource(single_deployment_target_options)

    # Assert
    assert result == {}
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_deployment_target_options.region, "codedeploy"
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_deployment_target_options.include,
        extra_context={
            "AccountId": single_deployment_target_options.account_id,
            "Region": single_deployment_target_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.DeploymentTargetActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployDeploymentTargetExporter,
    paginated_deployment_target_options: PaginatedCodeDeployDeploymentTargetRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockDeploymentPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield ["d-EXAMPLE11", "d-EXAMPLE22"]

    class MockTargetPaginator:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def paginate(self, deploymentId: str) -> AsyncGenerator[list[str], None]:
            self.calls.append(deploymentId)
            if deploymentId == "d-EXAMPLE11":
                yield ["i-0000000000000001", "i-0000000000000002"]
            elif deploymentId == "d-EXAMPLE22":
                yield ["i-0000000000000003"]

    target_paginator = MockTargetPaginator()

    def get_paginator(operation_name: str, *args: Any) -> Any:
        return (
            MockDeploymentPaginator()
            if operation_name == "list_deployments"
            else target_paginator
        )

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

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
    async for page in exporter.get_paginated_resources(
        paginated_deployment_target_options
    ):
        collected.append(page)

    # Assert
    assert collected == [
        [first_instance, second_instance],
        [third_instance],
    ]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_deployment_target_options.region, "codedeploy"
    )
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_deployments", "deployments"),
            call("list_deployment_targets", "targetIds"),
        ]
    )
    mock_input.assert_has_calls(
        [
            call(
                deployment_id="d-EXAMPLE11",
                items=["i-0000000000000001", "i-0000000000000002"],
                region=paginated_deployment_target_options.region,
                account_id=paginated_deployment_target_options.account_id,
            ),
            call(
                deployment_id="d-EXAMPLE22",
                items=["i-0000000000000003"],
                region=paginated_deployment_target_options.region,
                account_id=paginated_deployment_target_options.account_id,
            ),
        ]
    )
    mock_inspector.inspect.assert_has_calls(
        [
            call(
                mock_input.return_value,
                paginated_deployment_target_options.include,
                extra_context={
                    "AccountId": paginated_deployment_target_options.account_id,
                    "Region": paginated_deployment_target_options.region,
                },
            ),
            call(
                mock_input.return_value,
                paginated_deployment_target_options.include,
                extra_context={
                    "AccountId": paginated_deployment_target_options.account_id,
                    "Region": paginated_deployment_target_options.region,
                },
            ),
        ]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_empty_targets(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentTargetExporter,
    paginated_deployment_target_options: PaginatedCodeDeployDeploymentTargetRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockDeploymentPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield ["d-EXAMPLE11"]

    class MockTargetPaginator:
        async def paginate(self, deploymentId: str) -> AsyncGenerator[list[str], None]:
            yield []

    def get_paginator(operation_name: str, *args: Any) -> Any:
        return (
            MockDeploymentPaginator()
            if operation_name == "list_deployments"
            else MockTargetPaginator()
        )

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

    # Act
    results: list[dict[str, Any]] = []
    async for page in exporter.get_paginated_resources(
        paginated_deployment_target_options
    ):
        results.extend(page)

    # Assert
    assert results == []
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_deployments", "deployments"),
            call("list_deployment_targets", "targetIds"),
        ]
    )
    mock_inspector_class.return_value.inspect.assert_not_called()


@pytest.mark.asyncio
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_empty_deployments(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentTargetExporter,
    paginated_deployment_target_options: PaginatedCodeDeployDeploymentTargetRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockDeploymentPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield []

    class MockTargetPaginator:
        async def paginate(self, deploymentId: str) -> AsyncGenerator[list[str], None]:
            yield ["some-target"]

    def get_paginator(operation_name: str, *args: Any) -> Any:
        return (
            MockDeploymentPaginator()
            if operation_name == "list_deployments"
            else MockTargetPaginator()
        )

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

    # Act
    results: list[dict[str, Any]] = []
    async for page in exporter.get_paginated_resources(
        paginated_deployment_target_options
    ):
        results.extend(page)

    # Assert
    assert results == []
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_deployments", "deployments"),
        ]
    )
    mock_inspector_class.return_value.inspect.assert_not_called()
