import pytest
from unittest.mock import patch, MagicMock
from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from azure_devops.client.azure_devops_client import AzureDevopsClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext, event_context
from httpx import Response
from azure_devops.webhooks.webhook_event import WebhookEvent

MOCK_ORG_URL = "https://your_organization_url.com"
MOCK_PERSONAL_ACCESS_TOKEN = "personal_access_token"
MOCK_PROJECT_ID = "12345"
MOCK_PROJECT_NAME = "My Project"
EXPECTED_PROJECT = {"name": MOCK_PROJECT_NAME, "id": MOCK_PROJECT_ID}

MOCK_BOARD_ID = "board1"
MOCK_BOARD_NAME = "Board One"
EXPECTED_BOARDS = [
    {
        "id": MOCK_BOARD_ID,
        "name": MOCK_BOARD_NAME,
        "columns": [
            {"name": "To Do", "stateMappings": {"Bug": "New"}},
            {"name": "Doing", "stateMappings": {"Bug": "Active"}},
        ],
    }
]

EXPECTED_COLUMNS = [
    {
        "name": "To Do",
        "stateMappings": {"Bug": "New"},
        "__board": EXPECTED_BOARDS[0],
        "__stateType": "Bug",
        "__stateName": "New",
    },
    {
        "name": "Doing",
        "stateMappings": {"Bug": "Active"},
        "__board": EXPECTED_BOARDS[0],
        "__stateType": "Bug",
        "__stateName": "Active",
    },
]

EXPECTED_BOARDS_IN_ORG = [
    {**board, "__project": {"id": "proj1", "name": "Project One"}}
    for board in [
        {"id": "board1", "name": "Board One"},
        {"id": "board2", "name": "Board Two"},
    ]
]

EXPECTED_PROJECTS = [
    {"id": "proj1", "name": "Project One"},
    {"id": "proj2", "name": "Project Two"},
]

EXPECTED_TEAMS = [
    {"id": "team1", "name": "Team One"},
    {"id": "team2", "name": "Team Two"},
]

EXPECTED_MEMBERS = [
    {"id": "member1", "name": "Member One", "__teamId": "team1"},
    {"id": "member2", "name": "Member Two", "__teamId": "team1"},
]

EXPECTED_REPOSITORIES = [
    {"id": "repo1", "name": "Repo One", "isDisabled": False},
    {"id": "repo2", "name": "Repo Two", "isDisabled": False},
]

EXPECTED_PULL_REQUESTS = [
    {
        "pullRequestId": "pr1",
        "title": "Pull Request One",
        "repository": {"id": "repo1"},
    },
    {
        "pullRequestId": "pr2",
        "title": "Pull Request Two",
        "repository": {"id": "repo1"},
    },
]

EXPECTED_PIPELINES = [
    {"id": "pipeline1", "name": "Pipeline One", "__projectId": "proj1"},
    {"id": "pipeline2", "name": "Pipeline Two", "__projectId": "proj1"},
]

EXPECTED_POLICIES = [
    {"id": "policy1", "name": "Policy One", "__repository": {"id": "repo1"}},
    {"id": "policy2", "name": "Policy Two", "__repository": {"id": "repo1"}},
]

EXPECTED_WORK_ITEMS = [
    {
        "id": 1,
        "fields": {},
        "__projectId": "proj1",
        "__project": {"id": "proj1", "name": "Project One"},
    },
    {
        "id": 2,
        "fields": {},
        "__projectId": "proj1",
        "__project": {"id": "proj1", "name": "Project One"},
    },
    {
        "id": 3,
        "fields": {},
        "__projectId": "proj1",
        "__project": {"id": "proj1", "name": "Project One"},
    },
]

EXPECTED_PULL_REQUEST = {"id": "pr123", "title": "My Pull Request"}
EXPECTED_REPOSITORY = {"id": "repo123", "name": "My Repository"}

EXPECTED_WEBHOOK_EVENTS = [
    {
        "id": "sub1",
        "publisherId": "tfs",
        "eventType": "workitem.created",
        "consumerId": "webHooks",
        "consumerActionId": "httpRequest",
        "consumerInputs": None,
        "publisherInputs": None,
        "status": None,
    },
    {
        "id": "sub2",
        "publisherId": "tfs",
        "eventType": "git.push",
        "consumerId": "webHooks",
        "consumerActionId": "httpRequest",
        "consumerInputs": None,
        "publisherInputs": None,
        "status": None,
    },
]

EXPECTED_SUBSCRIPTION_CREATION_RESPONSE = {
    "id": "subscription123",
    "eventType": "git.push",
}

MOCK_FILE_CONTENT = b"file content"
MOCK_FILE_PATH = "/path/to/file.txt"
MOCK_REPOSITORY_ID = "repo123"
MOCK_BRANCH_NAME = "main"
MOCK_COMMIT_ID = "abc123"


async def async_generator(items: List[Any]) -> AsyncGenerator[Any, None]:
    for item in items:
        yield item


@pytest.fixture(autouse=True)
def mock_ocean_context() -> None:
    try:
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN,
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass


@pytest.fixture
def mock_event_context() -> Generator[MagicMock, None, None]:
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    mock_event._deadline = 999999999.0
    mock_event._aborted = False

    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event


@pytest.fixture
def mock_azure_client() -> AzureDevopsClient:
    return AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)


@pytest.mark.asyncio
async def test_get_single_project() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_PROJECT
        )

        # ACT
        project_id = MOCK_PROJECT_ID
        project = await client.get_single_project(project_id)

        # ASSERT
        assert project == EXPECTED_PROJECT
        mock_send_request.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/_apis/projects/{project_id}",
        )


@pytest.mark.asyncio
async def test_generate_projects(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_get_paginated_by_top_and_continuation_token(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [EXPECTED_PROJECTS[0]]
        yield [EXPECTED_PROJECTS[1]]

    with patch.object(
        client,
        "_get_paginated_by_top_and_continuation_token",
        side_effect=mock_get_paginated_by_top_and_continuation_token,
    ):
        async with event_context("test_event"):
            # ACT
            projects: List[Dict[str, Any]] = []
            async for project_batch in client.generate_projects():
                projects.extend(project_batch)

            # ASSERT
            assert projects == EXPECTED_PROJECTS


@pytest.mark.asyncio
async def test_generate_teams(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_get_paginated_by_top_and_skip(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [EXPECTED_TEAMS[0]]
        yield [EXPECTED_TEAMS[1]]

    with patch.object(
        client,
        "_get_paginated_by_top_and_skip",
        side_effect=mock_get_paginated_by_top_and_skip,
    ):
        async with event_context("test_event"):
            # ACT
            teams: List[Dict[str, Any]] = []
            async for team_batch in client.generate_teams():
                teams.extend(team_batch)

            # ASSERT
            assert teams == EXPECTED_TEAMS


@pytest.mark.asyncio
async def test_generate_members() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_generate_teams() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "team1", "name": "Team One", "projectId": "proj1"}]

    async def mock_get_paginated_by_top_and_skip(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if "members" in url:
            yield [
                {"id": "member1", "name": "Member One"},
                {"id": "member2", "name": "Member Two"},
            ]
        else:
            yield []

    with patch.object(client, "generate_teams", side_effect=mock_generate_teams):
        with patch.object(
            client,
            "_get_paginated_by_top_and_skip",
            side_effect=mock_get_paginated_by_top_and_skip,
        ):
            # ACT
            members: List[Dict[str, Any]] = []
            async for member_batch in client.generate_members():
                for member in member_batch:
                    member["__teamId"] = "team1"
                members.extend(member_batch)

            # ASSERT
            assert members == EXPECTED_MEMBERS


@pytest.mark.asyncio
async def test_generate_repositories(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    with patch.object(client, "generate_projects", side_effect=mock_generate_projects):
        with patch.object(client, "send_request") as mock_send_request:
            mock_send_request.return_value = Response(
                status_code=200,
                json={"value": EXPECTED_REPOSITORIES},
            )

            async with event_context("test_event"):
                # ACT
                repositories: List[Dict[str, Any]] = []
                async for repo_batch in client.generate_repositories(
                    include_disabled_repositories=False
                ):
                    repositories.extend(repo_batch)

                # ASSERT
                assert repositories == EXPECTED_REPOSITORIES


@pytest.mark.asyncio
async def test_generate_pull_requests(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_generate_repositories(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [
            {
                "id": "repo1",
                "name": "Repository One",
                "project": {"id": "proj1", "name": "Project One"},
            }
        ]

    async def mock_get_paginated_by_top_and_skip(
        url: str, additional_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if "pullrequests" in url:
            yield EXPECTED_PULL_REQUESTS
        else:
            yield []

    async with event_context("test_event"):

        with patch.object(
            client, "generate_repositories", side_effect=mock_generate_repositories
        ):
            with patch.object(
                client,
                "_get_paginated_by_top_and_skip",
                side_effect=mock_get_paginated_by_top_and_skip,
            ):
                # ACT
                pull_requests: List[Dict[str, Any]] = []
                async for pr_batch in client.generate_pull_requests():
                    pull_requests.extend(pr_batch)

                # ASSERT
                assert pull_requests == EXPECTED_PULL_REQUESTS


@pytest.mark.asyncio
async def test_generate_pipelines() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_paginated_by_top_and_continuation_token(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [
            {"id": "pipeline1", "name": "Pipeline One"},
            {"id": "pipeline2", "name": "Pipeline Two"},
        ]

    with patch.object(client, "generate_projects", side_effect=mock_generate_projects):
        with patch.object(
            client,
            "_get_paginated_by_top_and_continuation_token",
            side_effect=mock_get_paginated_by_top_and_continuation_token,
        ):
            # ACT
            pipelines: List[Dict[str, Any]] = []
            async for pipeline_batch in client.generate_pipelines():
                for pipeline in pipeline_batch:
                    pipeline["__projectId"] = "proj1"
                pipelines.extend(pipeline_batch)

            # ASSERT
            assert pipelines == EXPECTED_PIPELINES


@pytest.mark.asyncio
async def test_generate_repository_policies() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_generate_repositories(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [
            {
                "id": "repo1",
                "name": "Repository One",
                "project": {"id": "proj1", "name": "Project One"},
                "defaultBranch": "refs/heads/main",
            }
        ]

    with patch.object(
        client, "generate_repositories", side_effect=mock_generate_repositories
    ):
        with patch.object(client, "send_request") as mock_send_request:
            mock_send_request.return_value = Response(
                status_code=200,
                json={
                    "value": [
                        {"id": "policy1", "name": "Policy One"},
                        {"id": "policy2", "name": "Policy Two"},
                    ]
                },
            )

            # ACT
            policies: List[Dict[str, Any]] = []
            async for policy_batch in client.generate_repository_policies():
                for policy in policy_batch:
                    policy["__repository"] = {"id": "repo1"}
                policies.extend(policy_batch)

            # ASSERT
            assert policies == EXPECTED_POLICIES


@pytest.mark.asyncio
async def test_get_pull_request() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_PULL_REQUEST
        )

        # ACT
        pull_request_id = "pr123"
        pull_request = await client.get_pull_request(pull_request_id)

        # ASSERT
        assert pull_request == EXPECTED_PULL_REQUEST
        mock_send_request.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/_apis/git/pullrequests/{pull_request_id}",
        )


@pytest.mark.asyncio
async def test_get_repository() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_REPOSITORY
        )

        # ACT
        repository_id = "repo123"
        repository = await client.get_repository(repository_id)

        # ASSERT
        assert repository == EXPECTED_REPOSITORY
        mock_send_request.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/_apis/git/repositories/{repository_id}",
        )


@pytest.mark.asyncio
async def test_get_columns() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_get_boards_in_organization() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        yield EXPECTED_BOARDS

    with patch.object(
        client,
        "get_boards_in_organization",
        side_effect=mock_get_boards_in_organization,
    ):
        # ACT
        columns: List[Dict[str, Any]] = []
        async for column_batch in client.get_columns():
            columns.extend(column_batch)

        # ASSERT
        assert columns == EXPECTED_COLUMNS


@pytest.mark.asyncio
async def test_get_boards_in_organization(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_boards(project_id: str) -> List[Dict[str, Any]]:
        return [
            {"id": "board1", "name": "Board One"},
            {"id": "board2", "name": "Board Two"},
        ]

    async with event_context("test_event"):
        with patch.object(
            client, "generate_projects", side_effect=mock_generate_projects
        ):
            with patch.object(client, "_get_boards", side_effect=mock_get_boards):
                # ACT
                boards: List[Dict[str, Any]] = []
                async for board_batch in client.get_boards_in_organization():
                    boards.extend(board_batch)

                # ASSERT
                assert boards == EXPECTED_BOARDS_IN_ORG


@pytest.mark.asyncio
async def test_generate_subscriptions_webhook_events() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200,
            json={"value": EXPECTED_WEBHOOK_EVENTS},
        )

        # ACT
        events = await client.generate_subscriptions_webhook_events()

        # ASSERT
        assert [event.dict() for event in events] == EXPECTED_WEBHOOK_EVENTS


@pytest.mark.asyncio
async def test_create_subscription() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    webhook_event = WebhookEvent(
        id=None,
        eventType="git.push",
        publisherId="tfs",
        consumerId="webHooks",
        consumerActionId="httpRequest",
        status="enabled",
        consumerInputs={"url": "https://example.com/webhook"},
    )

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_SUBSCRIPTION_CREATION_RESPONSE
        )

        # ACT
        await client.create_subscription(webhook_event)

        # ASSERT
        mock_send_request.assert_called_once_with(
            "POST",
            f"{MOCK_ORG_URL}/_apis/hooks/subscriptions",
            params={"api-version": "7.1-preview.1"},
            headers={"Content-Type": "application/json"},
            data=webhook_event.json(),
        )


@pytest.mark.asyncio
async def test_delete_subscription() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    webhook_event = WebhookEvent(
        id="subscription123",
        publisherId="tfs",
        eventType="git.push",
        consumerId="webHooks",
        consumerActionId="httpRequest",
        status="enabled",
        consumerInputs={"url": "https://example.com/webhook"},
    )

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(status_code=204)

        # ACT
        await client.delete_subscription(webhook_event)

    # ASSERT
    mock_send_request.assert_called_once_with(
        "DELETE",
        f"{MOCK_ORG_URL}/_apis/hooks/subscriptions/{webhook_event.id}",
        headers={"Content-Type": "application/json"},
        params={"api-version": "7.1-preview.1"},
    )


@pytest.mark.asyncio
async def test_get_file_by_branch() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_response = Response(status_code=200, content=MOCK_FILE_CONTENT)
        mock_send_request.return_value = mock_response

        # ACT
        file_content = await client.get_file_by_branch(
            MOCK_FILE_PATH, MOCK_REPOSITORY_ID, MOCK_BRANCH_NAME
        )

        # ASSERT
        assert file_content == MOCK_FILE_CONTENT
        mock_send_request.assert_called_once_with(
            method="GET",
            url=f"{MOCK_ORG_URL}/_apis/git/repositories/{MOCK_REPOSITORY_ID}/items",
            params={
                "versionType": "Branch",
                "version": MOCK_BRANCH_NAME,
                "path": MOCK_FILE_PATH,
            },
        )


@pytest.mark.asyncio
async def test_get_file_by_commit() -> None:
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    # MOCK
    with patch.object(client, "send_request") as mock_send_request:
        mock_response = Response(status_code=200, content=MOCK_FILE_CONTENT)
        mock_send_request.return_value = mock_response

        # ACT
        file_content = await client.get_file_by_commit(
            MOCK_FILE_PATH, MOCK_REPOSITORY_ID, MOCK_COMMIT_ID
        )

        # ASSERT
        assert file_content == MOCK_FILE_CONTENT
        mock_send_request.assert_called_once_with(
            method="GET",
            url=f"{MOCK_ORG_URL}/_apis/git/repositories/{MOCK_REPOSITORY_ID}/items",
            params={
                "versionType": "Commit",
                "version": MOCK_COMMIT_ID,
                "path": MOCK_FILE_PATH,
            },
        )
