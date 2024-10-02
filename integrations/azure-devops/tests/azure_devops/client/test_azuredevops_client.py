import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError
from azure_devops.client.azure_devops_client import AzureDevopsClient
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.context.event import EventContext, event_context
from httpx import Response
from azure_devops.webhooks.webhook_event import WebhookEvent

# Example configuration for the tests
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
            {
                "name": "To Do",
                "stateMappings": {"Bug": "New"},
            },
            {
                "name": "Doing",
                "stateMappings": {"Bug": "Active"},
            },
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
    {"id": 1, "fields": {}, "__projectId": "proj1", "__project": {"id": "proj1", "name": "Project One"}},
    {"id": 2, "fields": {}, "__projectId": "proj1", "__project": {"id": "proj1", "name": "Project One"}},
    {"id": 3, "fields": {}, "__projectId": "proj1", "__project": {"id": "proj1", "name": "Project One"}},
]

EXPECTED_PULL_REQUEST = {"id": "pr123", "title": "My Pull Request"}
EXPECTED_REPOSITORY = {"id": "repo123", "name": "My Repository"}

EXPECTED_WEBHOOK_EVENTS = [
    {'id': 'sub1', 'publisherId': 'tfs', 'eventType': 'workitem.created', 'consumerId': 'webHooks', 'consumerActionId': 'httpRequest', 'consumerInputs': None, 'publisherInputs': None, 'status': None},
    {'id': 'sub2', 'publisherId': 'tfs', 'eventType': 'git.push', 'consumerId': 'webHooks', 'consumerActionId': 'httpRequest', 'consumerInputs': None, 'publisherInputs': None, 'status': None},
]

EXPECTED_SUBSCRIPTION_CREATION_RESPONSE = {"id": "subscription123", "eventType": "git.push"}

MOCK_FILE_CONTENT = b"file content"
MOCK_FILE_PATH = "/path/to/file.txt"
MOCK_REPOSITORY_ID = "repo123"
MOCK_BRANCH_NAME = "main"
MOCK_COMMIT_ID = "abc123"

async def async_generator(items):
    for item in items:
        yield items

# Mock the Ocean application and initialize the context
@pytest.fixture(autouse=True)
def mock_ocean_context():
    try:
        # Mock Ocean and its required attributes
        mock_ocean_app = MagicMock()
        mock_ocean_app.config.integration.config = {
            "organization_url": MOCK_ORG_URL,
            "personal_access_token": MOCK_PERSONAL_ACCESS_TOKEN
        }
        mock_ocean_app.integration_router = MagicMock()
        mock_ocean_app.port_client = MagicMock()
        # Initialize the ocean context with the mock Ocean object
        initialize_port_ocean_context(mock_ocean_app)
    except PortOceanContextAlreadyInitializedError:
        pass

# Mock event context to simulate event handling
@pytest.fixture
def mock_event_context():
    # Create a mock EventContext with attributes
    mock_event = MagicMock(spec=EventContext)
    mock_event.event_type = "test_event"
    mock_event.trigger_type = "manual"
    mock_event.attributes = {}
    # Explicitly set _deadline as a float
    mock_event._deadline = 999999999.0  # Large float value to represent a distant timeout
    mock_event._aborted = False

    mock_event.resource_config = MagicMock()
    mock_event.resource_config.selector = MagicMock()
    mock_event.resource_config.selector.wiql = MagicMock()

    # Patch the `event` LocalProxy
    with patch("port_ocean.context.event.event", mock_event):
        yield mock_event

@pytest.fixture
def mock_azure_client():
    """Fixture to create a mock AzureDevopsClient."""
    return AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

@pytest.mark.asyncio
async def test_get_single_project():
    # Mock the send_request method to return a successful response
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200,
            json=EXPECTED_PROJECT
        )

        # Call the function and assert the response
        project_id = MOCK_PROJECT_ID
        project = await client.get_single_project(project_id)

        assert project == EXPECTED_PROJECT
        mock_send_request.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/_apis/projects/{project_id}",
        )

@pytest.mark.asyncio
async def test_generate_projects(mock_event_context):
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_get_paginated_by_top_and_continuation_token(*args, **kwargs):
        yield [EXPECTED_PROJECTS[0]]
        yield [EXPECTED_PROJECTS[1]]

    with patch.object(
        client,
        "_get_paginated_by_top_and_continuation_token",
        side_effect=mock_get_paginated_by_top_and_continuation_token,
    ):
        async with event_context("test_event") as evt:
            projects = []
            async for project_batch in client.generate_projects():
                projects.extend(project_batch)

            assert projects == EXPECTED_PROJECTS

@pytest.mark.asyncio
async def test_generate_teams(mock_event_context):
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_get_paginated_by_top_and_skip(*args, **kwargs):
        yield [EXPECTED_TEAMS[0]]
        yield [EXPECTED_TEAMS[1]]

    with patch.object(
        client,
        "_get_paginated_by_top_and_skip",
        side_effect=mock_get_paginated_by_top_and_skip,
    ):
        async with event_context("test_event") as evt:
            teams = []
            async for team_batch in client.generate_teams():
                teams.extend(team_batch)

            assert teams == EXPECTED_TEAMS

@pytest.mark.asyncio
async def test_generate_members():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_generate_teams():
        yield [{"id": "team1", "name": "Team One", "projectId": "proj1"}]

    async def mock_get_paginated_by_top_and_skip(url, **kwargs):
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
            members = []
            async for member_batch in client.generate_members():
                for member in member_batch:
                    member["__teamId"] = "team1"
                members.extend(member_batch)

            assert members == EXPECTED_MEMBERS

@pytest.mark.asyncio
async def test_generate_repositories(mock_event_context):
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_generate_projects():
        yield [{"id": "proj1", "name": "Project One"}]

    async with event_context("test_event") as evt:
        with patch.object(client, "generate_projects", side_effect=mock_generate_projects):
            with patch.object(client, "send_request") as mock_send_request:
                mock_send_request.return_value = Response(
                    status_code=200,
                    json={
                        "value": EXPECTED_REPOSITORIES
                    },
                )

                repositories = []
                async for repo_batch in client.generate_repositories(
                    include_disabled_repositories=False
                ):
                    repositories.extend(repo_batch)

                assert repositories == EXPECTED_REPOSITORIES

@pytest.mark.asyncio
async def test_generate_pull_requests(mock_event_context):
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_generate_repositories(*args, **kwargs):
        yield [
            {
                "id": "repo1",
                "name": "Repository One",
                "project": {"id": "proj1", "name": "Project One"},
            }
        ]

    async def mock_get_paginated_by_top_and_skip(url, additional_params=None, **kwargs):
        if "pullrequests" in url:
            yield EXPECTED_PULL_REQUESTS
        else:
            yield []

    async with event_context("test_event") as evt:
        # Set resource_config if needed
        evt.resource_config = mock_event_context.resource_config

        with patch.object(
            client, "generate_repositories", side_effect=mock_generate_repositories
        ):
            with patch.object(
                client,
                "_get_paginated_by_top_and_skip",
                side_effect=mock_get_paginated_by_top_and_skip,
            ):
                pull_requests = []
                async for pr_batch in client.generate_pull_requests():
                    pull_requests.extend(pr_batch)

                assert pull_requests == EXPECTED_PULL_REQUESTS

@pytest.mark.asyncio
async def test_generate_pipelines():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_generate_projects():
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_paginated_by_top_and_continuation_token(url, **kwargs):
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
            pipelines = []
            async for pipeline_batch in client.generate_pipelines():
                for pipeline in pipeline_batch:
                    pipeline["__projectId"] = "proj1"
                pipelines.extend(pipeline_batch)

            assert pipelines == EXPECTED_PIPELINES

@pytest.mark.asyncio
async def test_generate_repository_policies():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_generate_repositories(*args, **kwargs):
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

            policies = []
            async for policy_batch in client.generate_repository_policies():
                for policy in policy_batch:
                    policy["__repository"] = {"id": "repo1"}
                policies.extend(policy_batch)

            assert policies == EXPECTED_POLICIES

@pytest.mark.asyncio
async def test_get_pull_request():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_PULL_REQUEST
        )

        pull_request_id = "pr123"
        pull_request = await client.get_pull_request(pull_request_id)

        assert pull_request == EXPECTED_PULL_REQUEST
        mock_send_request.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/_apis/git/pullrequests/{pull_request_id}",
        )

@pytest.mark.asyncio
async def test_get_repository():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_REPOSITORY
        )

        repository_id = "repo123"
        repository = await client.get_repository(repository_id)

        assert repository == EXPECTED_REPOSITORY
        mock_send_request.assert_called_once_with(
            "GET",
            f"{MOCK_ORG_URL}/_apis/git/repositories/{repository_id}",
        )

@pytest.mark.asyncio
async def test_get_columns():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_get_boards_in_organization():
        yield EXPECTED_BOARDS

    with patch.object(
        client, "get_boards_in_organization", side_effect=mock_get_boards_in_organization
    ):
        columns = []
        async for column_batch in client.get_columns():
            columns.extend(column_batch)

        assert columns == EXPECTED_COLUMNS

@pytest.mark.asyncio
async def test_get_boards_in_organization(mock_event_context):
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    async def mock_generate_projects():
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_boards(project_id):
        return [
            {"id": "board1", "name": "Board One"},
            {"id": "board2", "name": "Board Two"},
        ]

    async with event_context("test_event") as evt:
        with patch.object(client, "generate_projects", side_effect=mock_generate_projects):
            with patch.object(client, "_get_boards", side_effect=mock_get_boards):
                boards = []
                async for board_batch in client.get_boards_in_organization():
                    boards.extend(board_batch)

                assert boards == EXPECTED_BOARDS_IN_ORG

@pytest.mark.asyncio
async def test_generate_subscriptions_webhook_events():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)

    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200,
            json={
                "value": EXPECTED_WEBHOOK_EVENTS
            },
        )

        events = await client.generate_subscriptions_webhook_events()
        assert [event.dict() for event in events] == EXPECTED_WEBHOOK_EVENTS

@pytest.mark.asyncio
async def test_create_subscription():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    webhook_event = WebhookEvent(
        id=None,
        eventType="git.push",
        publisherId="tfs",
        resourceVersion="1.0",
        consumerId="webHooks",
        consumerActionId="httpRequest",
        scope="organization",
        status="enabled",
        url="https://example.com/webhook",
        description="Test subscription",
    )

    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(
            status_code=200, json=EXPECTED_SUBSCRIPTION_CREATION_RESPONSE
        )

        await client.create_subscription(webhook_event)

        mock_send_request.assert_called_once_with(
            "POST",
            f"{MOCK_ORG_URL}/_apis/hooks/subscriptions",
            params={"api-version": "7.1-preview.1"},
            headers={"Content-Type": "application/json"},
            data=webhook_event.json(),
        )

@pytest.mark.asyncio
async def test_delete_subscription():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    webhook_event = WebhookEvent(
        id="subscription123",
        publisherId="tfs",
        eventType="git.push",
        resourceVersion="1.0",
        consumerId="webHooks",
        consumerActionId="httpRequest",
        scope="organization",
        status="enabled",
        url="https://example.com/webhook",
        description="Test subscription",
    )

    with patch.object(client, "send_request") as mock_send_request:
        mock_send_request.return_value = Response(status_code=204)

        await client.delete_subscription(webhook_event)

    mock_send_request.assert_called_once_with(
        "DELETE",
        f"{MOCK_ORG_URL}/_apis/hooks/subscriptions/{webhook_event.id}",
        headers={"Content-Type": "application/json"},
        params={"api-version": "7.1-preview.1"},
    )

@pytest.mark.asyncio
async def test_get_file_by_branch():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    with patch.object(client, "send_request") as mock_send_request:
        mock_response = Response(status_code=200, content=MOCK_FILE_CONTENT)
        mock_send_request.return_value = mock_response

        file_content = await client.get_file_by_branch(
            MOCK_FILE_PATH, MOCK_REPOSITORY_ID, MOCK_BRANCH_NAME
        )

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
async def test_get_file_by_commit():
    client = AzureDevopsClient(MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN)
    with patch.object(client, "send_request") as mock_send_request:
        mock_response = Response(status_code=200, content=MOCK_FILE_CONTENT)
        mock_send_request.return_value = mock_response

        file_content = await client.get_file_by_commit(
            MOCK_FILE_PATH, MOCK_REPOSITORY_ID, MOCK_COMMIT_ID
        )

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
