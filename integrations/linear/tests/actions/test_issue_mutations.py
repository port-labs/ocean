from unittest.mock import AsyncMock, MagicMock

import pytest

from linear.core.mutations import IssueMutations
from linear.helpers.exceptions import LinearActionError


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["create", "update"])
async def test_issue_mutation_rejects_incomplete_response(operation: str) -> None:
    client = MagicMock()
    client.graphql.execute_mutation = AsyncMock(
        return_value={"issue": {"id": "issue-1"}}
    )
    mutations = IssueMutations(client)

    with pytest.raises(LinearActionError, match="incomplete"):
        if operation == "create":
            await mutations.create_issue({"teamId": "team-1", "title": "Bug"})
        else:
            await mutations.update_issue("ENG-1", {"title": "Bug"})
