from typing import Any

import asyncio
import pytest
from botocore.exceptions import ClientError

from aws.core.helpers.utils import (
    execute_concurrent_aws_operations,
    is_recoverable_aws_exception,
    is_throttling_exception,
    require_aws_resource,
)


class TestExecuteConcurrentAwsOperations:
    """Cover the alignment contract of the shared concurrent operation helper.

    Callers (ECR / ECS / EC2 actions) rely on the helper to return one entry
    per input item in the original order so that ``ResourceInspector``'s
    positional merge keeps enrichment data attached to the right resource.
    """

    @pytest.mark.asyncio
    async def test_returns_one_entry_per_input_on_success(self) -> None:
        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

        async def op(item: dict[str, Any]) -> dict[str, Any]:
            return {"value": item["id"].upper()}

        result = await execute_concurrent_aws_operations(
            input_items=items,
            operation_func=op,
            get_resource_identifier=lambda i: i["id"],
            operation_name="thing",
        )

        assert result == [{"value": "A"}, {"value": "B"}, {"value": "C"}]

    @pytest.mark.asyncio
    async def test_recoverable_error_yields_empty_placeholder(self) -> None:
        items = [{"id": "a"}]

        async def op(_: dict[str, Any]) -> dict[str, Any]:
            raise ClientError(
                {"Error": {"Code": "AccessDenied", "Message": "denied"}},
                "DescribeThing",
            )

        result = await execute_concurrent_aws_operations(
            input_items=items,
            operation_func=op,
            get_resource_identifier=lambda i: i["id"],
            operation_name="thing",
        )

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_recoverable_error_in_middle_preserves_alignment(self) -> None:
        """Middle item fails recoverably; surrounding items keep their slot."""
        items = [{"id": "a"}, {"id": "b"}, {"id": "c"}]

        async def op(item: dict[str, Any]) -> dict[str, Any]:
            if item["id"] == "b":
                raise ClientError(
                    {"Error": {"Code": "ResourceNotFoundException", "Message": "gone"}},
                    "DescribeThing",
                )
            return {"value": item["id"].upper()}

        result = await execute_concurrent_aws_operations(
            input_items=items,
            operation_func=op,
            get_resource_identifier=lambda i: i["id"],
            operation_name="thing",
        )

        assert len(result) == 3
        assert result[0] == {"value": "A"}
        assert result[1] == {}
        assert result[2] == {"value": "C"}

    @pytest.mark.asyncio
    async def test_non_recoverable_error_is_raised(self) -> None:
        items = [{"id": "a"}, {"id": "b"}]

        async def op(item: dict[str, Any]) -> dict[str, Any]:
            if item["id"] == "b":
                raise ClientError(
                    {"Error": {"Code": "InternalError", "Message": "boom"}},
                    "DescribeThing",
                )
            return {"value": item["id"]}

        with pytest.raises(ClientError) as exc_info:
            await execute_concurrent_aws_operations(
                input_items=items,
                operation_func=op,
                get_resource_identifier=lambda i: i["id"],
                operation_name="thing",
            )

        assert exc_info.value.response["Error"]["Code"] == "InternalError"

    @pytest.mark.asyncio
    async def test_empty_input_returns_empty_list(self) -> None:
        async def op(_: dict[str, Any]) -> dict[str, Any]:
            raise AssertionError("operation_func should not be called for empty input")

        result = await execute_concurrent_aws_operations(
            input_items=[],
            operation_func=op,
            get_resource_identifier=lambda i: i["id"],
            operation_name="thing",
        )

        assert result == []


class TestAwsExceptionHelpers:
    def test_is_throttling_exception(self) -> None:
        throttling_error = ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
            "DescribeTaskDefinition",
        )
        assert is_throttling_exception(throttling_error) is True
        assert is_recoverable_aws_exception(throttling_error) is True

    def test_is_throttling_error_code(self) -> None:
        throttling_error = ClientError(
            {"Error": {"Code": "Throttling", "Message": "Rate exceeded"}},
            "DescribeTaskDefinition",
        )
        assert is_throttling_exception(throttling_error) is True

    @pytest.mark.asyncio
    async def test_throttling_error_yields_empty_placeholder(self) -> None:
        items = [{"id": "a"}]

        async def op(_: dict[str, Any]) -> dict[str, Any]:
            raise ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "Rate exceeded"}},
                "DescribeTaskDefinition",
            )

        result = await execute_concurrent_aws_operations(
            input_items=items,
            operation_func=op,
            get_resource_identifier=lambda i: i["id"],
            operation_name="task definition",
        )

        assert result == [{}]

    @pytest.mark.asyncio
    async def test_concurrency_limit_bounds_parallelism(self) -> None:
        items = [{"id": str(i)} for i in range(5)]
        max_in_flight = 0
        current_in_flight = 0

        async def op(item: dict[str, Any]) -> dict[str, Any]:
            nonlocal max_in_flight, current_in_flight
            current_in_flight += 1
            max_in_flight = max(max_in_flight, current_in_flight)
            await asyncio.sleep(0.01)
            current_in_flight -= 1
            return {"value": item["id"]}

        result = await execute_concurrent_aws_operations(
            input_items=items,
            operation_func=op,
            get_resource_identifier=lambda i: i["id"],
            operation_name="thing",
            concurrency_limit=2,
        )

        assert result == [{"value": str(i)} for i in range(5)]
        assert max_in_flight <= 2


class TestRequireAwsResource:
    def test_returns_items_when_present(self) -> None:
        items = [{"id": "vol-1"}]
        assert (
            require_aws_resource(
                items,
                error_code="InvalidVolume.NotFound",
                message="Volume not found: vol-1",
                operation_name="DescribeVolumes",
            )
            == items
        )

    def test_raises_client_error_when_empty(self) -> None:
        with pytest.raises(ClientError) as exc_info:
            require_aws_resource(
                [],
                error_code="InvalidVolume.NotFound",
                message="Volume not found: vol-1",
                operation_name="DescribeVolumes",
            )

        assert exc_info.value.response["Error"]["Code"] == "InvalidVolume.NotFound"
        assert exc_info.value.operation_name == "DescribeVolumes"

    def test_raises_client_error_when_none(self) -> None:
        with pytest.raises(ClientError) as exc_info:
            require_aws_resource(
                None,
                error_code="ClusterNotFoundException",
                message="Cluster not found: my-cluster",
                operation_name="DescribeClusters",
            )

        assert exc_info.value.response["Error"]["Code"] == "ClusterNotFoundException"
