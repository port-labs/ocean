import pytest
from integrations.spacelift.utils.spacelift import fetch_stacks


@pytest.mark.asyncio
async def test_fetch_stacks(monkeypatch):
    # Mocked response to simulate GraphQL query result
    mock_response = {
        "data": {
            "stacks": [
                {
                    "id": "abc",
                    "name": "Test",
                    "branch": "main",
                    "repository": "repo",
                    "projectRoot": "/",
                    "space": {
                        "id": "sp1",
                        "name": "DevOps"
                    }
                }
            ]
        }
    }

    async def mock_query(self, query, variables=None):
        return mock_response

    monkeypatch.setattr(
        "resources.stacks.SpaceliftGraphQLClient.query",
        mock_query
    )

    # Call the function to fetch stacks
    stacks = await fetch_stacks()

    assert len(stacks) == 1
    assert stacks[0]["identifier"] == "abc"
    assert stacks[0]["title"] == "Test"
    assert stacks[0]["properties"]["repository"] == "repo"
