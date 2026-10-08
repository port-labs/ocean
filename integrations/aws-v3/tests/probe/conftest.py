from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator
from unittest.mock import AsyncMock, MagicMock

import pytest
from botocore.exceptions import ClientError

from port_ocean.core.probe import ProbeContext


def client_error(code: str, operation: str = "SimulatePrincipalPolicy") -> ClientError:
    return ClientError(
        {"Error": {"Code": code, "Message": code}},
        operation,
    )


@pytest.fixture
def probe_context() -> ProbeContext:
    context = ProbeContext()
    context.reporter = MagicMock()
    context.reporter.report = AsyncMock()
    return context


def make_session(
    *,
    account_id: str = "111122223333",
    caller_arn: str | None = None,
    simulate_response: dict[str, Any] | None = None,
    simulate_side_effect: Exception | None = None,
    context_keys: list[str] | None = None,
    context_keys_side_effect: Exception | None = None,
) -> MagicMock:
    session = MagicMock()
    sts = AsyncMock()
    sts.get_caller_identity = AsyncMock(
        return_value={
            "Account": account_id,
            "Arn": caller_arn
            or f"arn:aws:sts::{account_id}:assumed-role/PortOceanReadRole/session",
            "UserId": "AIDACKCEVSQ6C2EXAMPLE",
        }
    )

    iam = AsyncMock()
    if context_keys_side_effect is not None:
        iam.get_context_keys_for_principal_policy = AsyncMock(
            side_effect=context_keys_side_effect
        )
    else:
        iam.get_context_keys_for_principal_policy = AsyncMock(
            return_value={"ContextKeyNames": context_keys or ["aws:RequestedRegion"]}
        )

    if simulate_side_effect is not None:
        iam.simulate_principal_policy = AsyncMock(side_effect=simulate_side_effect)
    else:
        iam.simulate_principal_policy = AsyncMock(
            return_value=simulate_response
            or {
                "EvaluationResults": [
                    {
                        "EvalActionName": "ec2:DescribeInstances",
                        "EvalDecision": "allowed",
                    },
                    {
                        "EvalActionName": "s3:ListAllMyBuckets",
                        "EvalDecision": "allowed",
                    },
                ],
                "IsTruncated": False,
            }
        )

    @asynccontextmanager
    async def create_client(
        service_name: str, **_kwargs: Any
    ) -> AsyncGenerator[Any, None]:
        if service_name == "sts":
            yield sts
        elif service_name == "iam":
            yield iam
        else:
            raise NotImplementedError(service_name)

    session.create_client = create_client
    session._sts = sts
    session._iam = iam
    return session
