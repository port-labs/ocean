from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest

from aws.core.exporters.codedeploy.deployment_group.exporter import (
    CodeDeployDeploymentGroupExporter,
)
from aws.core.exporters.codedeploy.deployment_group.models import (
    SingleCodeDeployDeploymentGroupRequest,
    PaginatedCodeDeployDeploymentGroupRequest,
)

patch_prefix = "aws.core.exporters.codedeploy.deployment_group.exporter"


@pytest.fixture
def exporter() -> CodeDeployDeploymentGroupExporter:
    """Create a CodeDeployDeploymentGroupExporter instance for testing."""
    return CodeDeployDeploymentGroupExporter(AsyncMock())


@pytest.fixture
def single_deployment_group_options() -> SingleCodeDeployDeploymentGroupRequest:
    return SingleCodeDeployDeploymentGroupRequest(
        region="us-east-1",
        account_id="123456789012",
        application_name="my-app",
        deployment_group_name="my-group",
        include=[],
    )


@pytest.fixture
def paginated_deployment_group_options() -> PaginatedCodeDeployDeploymentGroupRequest:
    return PaginatedCodeDeployDeploymentGroupRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.DeploymentGroupActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployDeploymentGroupExporter,
    single_deployment_group_options: SingleCodeDeployDeploymentGroupRequest,
) -> None:
    # Arrange
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector
    mock_inspector.inspect.return_value = [MagicMock()]

    # Act
    result = await exporter.get_resource(single_deployment_group_options)

    # Assert
    assert result == mock_inspector.inspect.return_value[0]
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_deployment_group_options.region, "codedeploy"
    )
    mock_input.assert_called_once_with(
        app_name=single_deployment_group_options.application_name,
        items=[single_deployment_group_options.deployment_group_name],
        region=single_deployment_group_options.region,
        account_id=single_deployment_group_options.account_id,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_deployment_group_options.include,
        extra_context={
            "AccountId": single_deployment_group_options.account_id,
            "Region": single_deployment_group_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.DeploymentGroupActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_resource_empty_inspection_returns_empty_dict(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployDeploymentGroupExporter,
    single_deployment_group_options: SingleCodeDeployDeploymentGroupRequest,
) -> None:
    # Arrange
    mock_inspector = AsyncMock()
    mock_inspector.inspect.return_value = []
    mock_inspector_class.return_value = mock_inspector

    # Act
    result = await exporter.get_resource(single_deployment_group_options)

    # Assert
    assert result == {}
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_deployment_group_options.region, "codedeploy"
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_deployment_group_options.include,
        extra_context={
            "AccountId": single_deployment_group_options.account_id,
            "Region": single_deployment_group_options.region,
        },
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.DeploymentGroupActionInput")
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployDeploymentGroupExporter,
    paginated_deployment_group_options: PaginatedCodeDeployDeploymentGroupRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockAppPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield ["app-a", "app-b"]

    class MockGroupPaginator:
        def __init__(self) -> None:
            self.calls: list[str] = []

        async def paginate(
            self, applicationName: str
        ) -> AsyncGenerator[list[str], None]:
            self.calls.append(applicationName)
            if applicationName == "app-a":
                yield ["group-a1", "group-a2"]
            elif applicationName == "app-b":
                yield ["group-b1"]

    group_paginator = MockGroupPaginator()

    def get_paginator(operation_name: str, *args: Any) -> Any:
        return (
            MockAppPaginator()
            if operation_name == "list_applications"
            else group_paginator
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
        paginated_deployment_group_options
    ):
        collected.append(page)

    # Assert
    assert collected == [
        [first_instance, second_instance],
        [third_instance],
    ]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_deployment_group_options.region, "codedeploy"
    )
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_applications", "applications"),
            call("list_deployment_groups", "deploymentGroups"),
        ]
    )
    mock_input.assert_has_calls(
        [
            call(
                app_name="app-a",
                items=["group-a1", "group-a2"],
                region=paginated_deployment_group_options.region,
                account_id=paginated_deployment_group_options.account_id,
            ),
            call(
                app_name="app-b",
                items=["group-b1"],
                region=paginated_deployment_group_options.region,
                account_id=paginated_deployment_group_options.account_id,
            ),
        ]
    )
    mock_inspector.inspect.assert_has_calls(
        [
            call(
                mock_input.return_value,
                paginated_deployment_group_options.include,
                extra_context={
                    "AccountId": paginated_deployment_group_options.account_id,
                    "Region": paginated_deployment_group_options.region,
                },
            ),
            call(
                mock_input.return_value,
                paginated_deployment_group_options.include,
                extra_context={
                    "AccountId": paginated_deployment_group_options.account_id,
                    "Region": paginated_deployment_group_options.region,
                },
            ),
        ]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_resources_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentGroupExporter,
    paginated_deployment_group_options: PaginatedCodeDeployDeploymentGroupRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockAppPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield ["app-a"]

    class MockGroupPaginator:
        async def paginate(
            self, applicationName: str
        ) -> AsyncGenerator[list[str], None]:
            yield []

    def get_paginator(operation_name: str, *args: Any) -> Any:
        return (
            MockAppPaginator()
            if operation_name == "list_applications"
            else MockGroupPaginator()
        )

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

    # Act
    results: list[dict[str, Any]] = []
    async for page in exporter.get_paginated_resources(
        paginated_deployment_group_options
    ):
        results.extend(page)

    # Assert
    assert results == []
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_applications", "applications"),
            call("list_deployment_groups", "deploymentGroups"),
        ]
    )
    mock_inspector_class.return_value.inspect.assert_not_called()


@pytest.mark.asyncio
@patch(f"{patch_prefix}.AioBaseClientProxy")
@patch(f"{patch_prefix}.ResourceInspector")
async def test_get_paginated_apps_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    exporter: CodeDeployDeploymentGroupExporter,
    paginated_deployment_group_options: PaginatedCodeDeployDeploymentGroupRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockAppPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield []

    class MockGroupPaginator:
        async def paginate(
            self, applicationName: str
        ) -> AsyncGenerator[list[str], None]:
            yield ["random-group"]

    def get_paginator(operation_name: str, *args: Any) -> Any:
        return (
            MockAppPaginator()
            if operation_name == "list_applications"
            else MockGroupPaginator()
        )

    mock_proxy.get_paginator = MagicMock(side_effect=get_paginator)

    # Act
    results: list[dict[str, Any]] = []
    async for page in exporter.get_paginated_resources(
        paginated_deployment_group_options
    ):
        results.extend(page)

    # Assert
    assert results == []
    mock_proxy.get_paginator.assert_has_calls(
        [
            call("list_applications", "applications"),
            call("list_deployment_groups", "deploymentGroups"),
        ]
    )
    mock_inspector_class.return_value.inspect.assert_not_called()
