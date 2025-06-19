from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from typing import Any

import aioboto3
from aws.core.handlers._base_handler import BaseResyncHandler
from aws.core._context import ResyncContext
from aws.auth.account import AWSSessionStrategy
from aws.helpers.models import MaterializedResource


class AccountResyncHandler(BaseResyncHandler):
    """Handler for fetching AWS account information."""

    async def _fetch_batches(
        self, session: aioboto3.Session
    ) -> AsyncIterator[Sequence[Any]]:
        """Fetch account information using STS GetCallerIdentity."""
        sts_client = await self._get_client(session, "sts")
        response = await sts_client.get_caller_identity()
        yield [response]

    async def _materialise_item(self, item: dict[str, Any]) -> MaterializedResource:
        """Transform raw account data into Port-ready format."""
        return self._ctx.enrich(
            {
                "identifier": item["Account"],
                "arn": item["Arn"],
                "user_id": item["UserId"],
                "type": "AWS Account",
                "properties": {
                    "account_id": item["Account"],
                    "arn": item["Arn"],
                    "user_id": item["UserId"],
                },
            }
        )
