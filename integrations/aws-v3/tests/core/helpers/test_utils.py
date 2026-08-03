from typing import Any

import pytest
from botocore.exceptions import ClientError

from aws.core.helpers.utils import execute_concurrent_aws_operations


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
