from typing import AsyncGenerator, Any
from unittest.mock import AsyncMock, MagicMock, patch, call
import pytest
from aws.core.exporters.codedeploy.application.exporter import (
    CodeDeployApplicationExporter,
)
from aws.core.exporters.codedeploy.application.models import (
    SingleCodeDeployApplicationRequest,
    PaginatedCodeDeployApplicationRequest,
)

patch_prefix = "aws.core.exporters.codedeploy.application.exporter."


@pytest.fixture
def exporter() -> CodeDeployApplicationExporter:
    """Create a CodeDeployApplicationExporter instance for testing."""
    return CodeDeployApplicationExporter(AsyncMock())


@pytest.fixture
def single_application_options() -> SingleCodeDeployApplicationRequest:
    return SingleCodeDeployApplicationRequest(
        region="us-east-1",
        account_id="123456789012",
        application_name="abc",
        include=[],
    )


@pytest.fixture
def paginated_application_options() -> PaginatedCodeDeployApplicationRequest:
    return PaginatedCodeDeployApplicationRequest(
        region="us-east-1", account_id="123456789012", include=[]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}CodeDeployApplicationActionInput")
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_resource_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployApplicationExporter,
    single_application_options: SingleCodeDeployApplicationRequest,
) -> None:
    # Arrange
    mock_inspector = AsyncMock()
    mock_inspector_class.return_value = mock_inspector
    mock_inspector.inspect.return_value = [MagicMock()]

    # Act
    result = await exporter.get_resource(single_application_options)

    # Assert
    assert result == mock_inspector.inspect.return_value[0]
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_application_options.region, "codedeploy"
    )
    mock_input.assert_called_once_with(
        items=[single_application_options.application_name],
        region=single_application_options.region,
        account_id=single_application_options.account_id,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value, single_application_options.include
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}CodeDeployApplicationActionInput")
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_resource_empty_inspection_returns_empty_dict(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployApplicationExporter,
    single_application_options: SingleCodeDeployApplicationRequest,
) -> None:
    # Arrange
    mock_inspector = AsyncMock()
    mock_inspector.inspect.return_value = []
    mock_inspector_class.return_value = mock_inspector

    # Act
    result = await exporter.get_resource(single_application_options)

    # Assert
    assert result == {}
    mock_proxy_class.assert_called_once_with(
        exporter.session, single_application_options.region, "codedeploy"
    )
    mock_input.assert_called_once_with(
        items=[single_application_options.application_name],
        region=single_application_options.region,
        account_id=single_application_options.account_id,
    )
    mock_inspector.inspect.assert_called_once_with(
        mock_input.return_value,
        single_application_options.include,
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}CodeDeployApplicationActionInput")
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_paginated_resources_success(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployApplicationExporter,
    paginated_application_options: PaginatedCodeDeployApplicationRequest,
) -> None:
    # Arrange
    mock_proxy = AsyncMock()
    mock_proxy_class.return_value.__aenter__.return_value = mock_proxy

    class MockPaginator:
        async def paginate(self) -> AsyncGenerator[list[str], None]:
            yield ["app-b", "app-a"]
            yield ["app-c"]

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

    # Arrange
    collected: list[list[dict[str, Any]]] = []
    async for page in exporter.get_paginated_resources(paginated_application_options):
        collected.append(page)

    # Assert
    assert collected == [
        [first_instance, second_instance],
        [third_instance],
    ]

    mock_proxy_class.assert_called_once_with(
        exporter.session, paginated_application_options.region, "codedeploy"
    )
    mock_proxy.get_paginator.assert_called_once_with(
        "list_applications", "applications"
    )
    mock_input.assert_has_calls(
        [
            call(
                items=["app-a", "app-b"],
                region=paginated_application_options.region,
                account_id=paginated_application_options.account_id,
            ),
            call(
                items=["app-c"],
                region=paginated_application_options.region,
                account_id=paginated_application_options.account_id,
            ),
        ]
    )
    mock_inspector.inspect.assert_has_calls(
        [
            call(
                mock_input.return_value,
                paginated_application_options.include,
                extra_context={
                    "AccountId": paginated_application_options.account_id,
                    "Region": paginated_application_options.region,
                },
            ),
            call(
                mock_input.return_value,
                paginated_application_options.include,
                extra_context={
                    "AccountId": paginated_application_options.account_id,
                    "Region": paginated_application_options.region,
                },
            ),
        ]
    )


@pytest.mark.asyncio
@patch(f"{patch_prefix}CodeDeployApplicationActionInput")
@patch(f"{patch_prefix}AioBaseClientProxy")
@patch(f"{patch_prefix}ResourceInspector")
async def test_get_paginated_resources_empty(
    mock_inspector_class: MagicMock,
    mock_proxy_class: MagicMock,
    mock_input: MagicMock,
    exporter: CodeDeployApplicationExporter,
    paginated_application_options: PaginatedCodeDeployApplicationRequest,
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
    async for page in exporter.get_paginated_resources(paginated_application_options):
        results.extend(page)

    # Assert
    assert results == []
    mock_proxy.get_paginator.assert_called_once_with(
        "list_applications", "applications"
    )
    mock_input.assert_not_called()
    mock_inspector_class.return_value.inspect.assert_not_called()
