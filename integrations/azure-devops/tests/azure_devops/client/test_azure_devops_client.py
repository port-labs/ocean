from typing import Any, AsyncGenerator, Dict, Generator, List, Optional
from unittest.mock import MagicMock, patch, AsyncMock

import pytest
from httpx import Request, Response
from port_ocean.context.event import EventContext, event_context
from port_ocean.context.ocean import initialize_port_ocean_context
from port_ocean.exceptions.context import PortOceanContextAlreadyInitializedError

from azure_devops.client.azure_devops_client import AzureDevopsClient
from azure_devops.webhooks.webhook_event import WebhookSubscription
from azure_devops.misc import FolderPattern, RepositoryBranchMapping

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
    {"id": "team1", "name": "Team One", "projectId": "proj1"},
    {"id": "team2", "name": "Team Two", "projectId": "proj2"},
]

EXPECTED_MEMBERS = [
    {"id": "member1", "name": "Member One", "__teamId": "team1"},
    {"id": "member2", "name": "Member Two", "__teamId": "team1"},
]

EXPECTED_REPOSITORIES = [
    {
        "id": "repo1",
        "name": "Repo One",
        "isDisabled": False,
        "project": {
            "state": "wellFormed",
        },
    },
    {
        "id": "repo2",
        "name": "Repo Two",
        "isDisabled": False,
        "project": {
            "state": "wellFormed",
        },
    },
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

EXPECTED_RELEASES = [
    {
        "id": 18,
        "name": "Release-18",
        "status": "abandoned",
        "createdOn": "2017-06-16T01:36:20.397Z",
        "modifiedOn": "2017-06-16T01:36:21.07Z",
        "description": "Creating Sample release",
        "reason": "manual",
        "releaseNameFormat": "Release-$(rev:r)",
        "keepForever": False,
        "projectReference": {"id": "proj1", "name": "Project One"},
    }
]

MOCK_FILE_CONTENT = b"file content"
MOCK_FILE_PATH = "/path/to/file.txt"
MOCK_REPOSITORY_ID = "repo123"
MOCK_BRANCH_NAME = "main"
MOCK_COMMIT_ID = "abc123"
MOCK_AUTH_USERNAME = "port"

EXPECTED_TREE_ITEMS = [
    {
        "objectId": "abc123",
        "gitObjectType": "tree",
        "path": "/src/main",
    },
    {
        "objectId": "def456",
        "gitObjectType": "tree",
        "path": "/src/main/code",
    },
    {
        "objectId": "ghi789",
        "gitObjectType": "blob",
        "path": "/src/main/code/file.txt",
    },
]


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
        mock_ocean_app.cache_provider = AsyncMock()
        mock_ocean_app.cache_provider.get.return_value = None
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
    return AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )


@pytest.fixture
def sample_folder_patterns() -> List[FolderPattern]:
    return [
        FolderPattern(
            path="/src/main",
            repos=[
                RepositoryBranchMapping(name="repo1", branch="main"),
                RepositoryBranchMapping(name="repo2", branch="main"),
            ],
        ),
        FolderPattern(
            path="/docs",
            repos=[
                RepositoryBranchMapping(name="repo2", branch="main"),
                RepositoryBranchMapping(name="repo3", branch="develop"),
            ],
        ),
    ]


@pytest.mark.parametrize(
    "repository,is_healthy",
    [
        ({"id": "repo1", "name": "Repo One", "isDisabled": False}, True),
        ({"id": "repo2", "name": "Repo Two", "isDisabled": True}, False),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": False,
                "project": {
                    "state": "wellFormed",
                },
            },
            True,
        ),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": False,
                "project": {
                    "state": "deleted",
                },
            },
            False,
        ),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": False,
                "project": {
                    "state": "deleting",
                },
                "defaultBranch": "refs/heads/main",
            },
            False,
        ),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": False,
                "project": {
                    "state": "new",
                },
                "defaultBranch": "refs/heads/main",
            },
            False,
        ),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": False,
                "project": {
                    "state": "createPending",
                },
                "defaultBranch": "refs/heads/main",
            },
            False,
        ),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": True,
                "project": {
                    "state": "wellFormed",
                },
                "defaultBranch": "refs/heads/main",
            },
            False,
        ),
        (
            {
                "id": "repo2",
                "name": "Repo Two",
                "isDisabled": False,
                "project": {
                    "state": "wellFormed",
                },
                "defaultBranch": "refs/heads/main",
            },
            True,
        ),
    ],
)
def test_repository_is_healthy(repository: Dict[str, Any], is_healthy: bool) -> None:
    assert AzureDevopsClient._repository_is_healthy(repository) == is_healthy


@pytest.mark.asyncio
async def test_get_single_project() -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
async def test_get_team_members() -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    test_team = {"id": "team1", "projectId": "proj1", "name": "Team One"}

    expected_members = [
        {"id": "member1", "displayName": "Member One"},
        {"id": "member2", "displayName": "Member Two"},
    ]

    async def mock_get_paginated_by_top_and_skip(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        assert (
            f"projects/{test_team['projectId']}/teams/{test_team['id']}/members" in url
        )
        yield expected_members

    with patch.object(
        client,
        "_get_paginated_by_top_and_skip",
        side_effect=mock_get_paginated_by_top_and_skip,
    ):
        # ACT
        members = await client.get_team_members(test_team)

        # ASSERT
        assert members == expected_members


@pytest.mark.asyncio
async def test_enrich_teams_with_members() -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    test_teams = [
        {"id": "team1", "projectId": "proj1", "name": "Team One"},
        {"id": "team2", "projectId": "proj1", "name": "Team Two"},
    ]

    team1_members = [{"id": "member1", "displayName": "Member One"}]
    team2_members = [{"id": "member2", "displayName": "Member Two"}]

    async def mock_get_team_members(team: Dict[str, Any]) -> List[Dict[str, Any]]:
        return team1_members if team["id"] == "team1" else team2_members

    with patch.object(
        client,
        "get_team_members",
        side_effect=mock_get_team_members,
    ):
        # ACT
        enriched_teams = await client.enrich_teams_with_members(test_teams)

        # ASSERT
        assert len(enriched_teams) == 2
        assert enriched_teams[0]["__members"] == team1_members
        assert enriched_teams[1]["__members"] == team2_members


@pytest.mark.asyncio
async def test_generate_repositories(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
                pull_requests: List[Dict[str, Any]] = []
                async for pr_batch in client.generate_pull_requests():
                    pull_requests.extend(pr_batch)
                assert pull_requests == EXPECTED_PULL_REQUESTS


@pytest.mark.asyncio
async def test_generate_projects_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with patch.object(client._client, "request", side_effect=mock_make_request):
            projects: List[Dict[str, Any]] = []
            async for project_batch in client.generate_projects():
                projects.extend(project_batch)
            assert not projects


@pytest.mark.asyncio
async def test_generate_teams_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with patch.object(client._client, "request", side_effect=mock_make_request):
            teams: List[Dict[str, Any]] = []
            async for team_batch in client.generate_teams():
                teams.extend(team_batch)

            assert not teams


@pytest.mark.asyncio
async def test_generate_repositories_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with patch.object(
            client, "generate_projects", side_effect=mock_generate_projects
        ):
            with patch.object(client._client, "request", side_effect=mock_make_request):
                repositories: List[Dict[str, Any]] = []
                async for repo_batch in client.generate_repositories():
                    repositories.extend(repo_batch)
                assert not repositories


@pytest.mark.asyncio
async def test_generate_members_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async def mock_get_teams(
        *args: Any, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        for team in EXPECTED_TEAMS:
            yield [team]

    async with event_context("test_event"):
        with (
            patch.object(client, "generate_teams", side_effect=mock_get_teams),
            patch.object(client._client, "request", side_effect=mock_make_request),
        ):
            members: List[Dict[str, Any]] = []
            async for member_batch in client.generate_members():
                members.extend(member_batch)
            assert not members


@pytest.mark.asyncio
async def test_generate_users_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with patch.object(client._client, "request", side_effect=mock_make_request):
            users: List[Dict[str, Any]] = []
            async for user_batch in client.generate_users():
                users.extend(user_batch)
            assert not users


@pytest.mark.asyncio
async def test_generate_pull_requests_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with (
            patch.object(
                client, "generate_repositories", side_effect=mock_generate_repositories
            ),
            patch.object(client._client, "request", side_effect=mock_make_request),
        ):
            pull_requests: List[Dict[str, Any]] = []
            async for pr_batch in client.generate_pull_requests():
                pull_requests.extend(pr_batch)

            assert not pull_requests


@pytest.mark.asyncio
async def test_generate_pipelines_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with (
            patch.object(
                client, "generate_projects", side_effect=mock_generate_projects
            ),
            patch.object(client._client, "request", side_effect=mock_make_request),
        ):
            pipelines: List[Dict[str, Any]] = []
            async for pipeline_batch in client.generate_pipelines():
                pipelines.extend(pipeline_batch)

            assert not pipelines


@pytest.mark.asyncio
async def test_generate_repository_policies_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with (
            patch.object(
                client, "generate_repositories", side_effect=mock_generate_repositories
            ),
            patch.object(client._client, "request", side_effect=mock_make_request),
        ):
            policies: List[Dict[str, Any]] = []
            async for policy_batch in client.generate_repository_policies():
                policies.extend(policy_batch)

            assert not policies


@pytest.mark.asyncio
async def test_generate_releases_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://google.com"))

    async with event_context("test_event"):
        with (
            patch.object(
                client, "generate_projects", side_effect=mock_generate_projects
            ),
            patch.object(client._client, "request", side_effect=mock_make_request),
        ):
            releases: List[Dict[str, Any]] = []
            async for release_batch in client.generate_releases():
                releases.extend(release_batch)

            assert not releases


@pytest.mark.asyncio
async def test_generate_work_items_will_skip_404(mock_event_context: MagicMock) -> None:
    """
    Tests that if a 404 is encountered anywhere in the pipeline (e.g. retrieving the WIQL
    or fetching work items), the client logs a warning and yields no items.
    """
    client = AzureDevopsClient("https://fake_org_url.com", "fake_pat", "fake_username")

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://fake_url.com"))

    async with event_context("test_event"):
        with patch.object(client._client, "request", side_effect=mock_make_request):
            collected_items: List[Dict[str, Any]] = []
            async for item_batch in client.generate_work_items(wiql=None, expand="all"):
                collected_items.extend(item_batch)
            assert not collected_items


@pytest.mark.asyncio
async def test_get_columns_will_skip_404(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://fake_url.com"))

    async with event_context("test_event"):
        columns_collected = []
        with patch.object(client._client, "request", side_effect=mock_make_request):
            async for col_batch in client.get_columns():
                columns_collected.extend(col_batch)

        assert columns_collected == []


@pytest.mark.asyncio
async def test_get_boards_in_organization_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://fake_url.com"))

    boards_collected = []
    async with event_context("test_event"):
        with patch.object(client._client, "request", side_effect=mock_make_request):
            async for board_batch in client.get_boards_in_organization():
                boards_collected.extend(board_batch)

        assert boards_collected == []


@pytest.mark.asyncio
async def test_generate_subscriptions_webhook_events_will_skip_404(
    mock_event_context: MagicMock,
) -> None:
    """
    generate_subscriptions_webhook_events fetches a single endpoint and returns a list of WebhookSubscription.
    On 404, it should skip and return [].
    """
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async with event_context("test_event"):
        with patch.object(client, "send_request") as mock_send_request:
            # Return a 404 plus minimal JSON to avoid JSONDecodeError
            mock_send_request.return_value = Response(
                status_code=404,
                json={},
                request=Request("GET", "https://fake_url.com"),
            )

            events = await client.generate_subscriptions_webhook_events()
            assert events == []


@pytest.mark.asyncio
async def test_get_file_by_branch_will_skip_404(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_make_request(**kwargs: Any) -> Response:
        return Response(status_code=404, request=Request("GET", "https://fake_url.com"))

    async with event_context("test_event"):
        with patch.object(client._client, "request", side_effect=mock_make_request):
            content = await client.get_file_by_branch(
                MOCK_FILE_PATH, MOCK_REPOSITORY_ID, MOCK_BRANCH_NAME
            )
            # The code warns on 404 and returns empty bytes
            assert content == b""


@pytest.mark.asyncio
async def test_generate_pipelines() -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
async def test_generate_releases(mock_event_context: MagicMock) -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    # MOCK
    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_paginated_by_top_and_continuation_token(
        url: str, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if "releases" in url:
            yield EXPECTED_RELEASES
        else:
            yield []

    async with event_context("test_event"):
        with patch.object(
            client, "generate_projects", side_effect=mock_generate_projects
        ):
            with patch.object(
                client,
                "_get_paginated_by_top_and_continuation_token",
                side_effect=mock_get_paginated_by_top_and_continuation_token,
            ):
                # ACT
                releases: List[Dict[str, Any]] = []
                async for release_batch in client.generate_releases():
                    releases.extend(release_batch)

                # ASSERT
                assert releases == EXPECTED_RELEASES


@pytest.mark.asyncio
async def test_get_pull_request() -> None:
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    # MOCK
    async def mock_generate_projects() -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"id": "proj1", "name": "Project One"}]

    async def mock_get_boards(
        project_id: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [
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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )
    webhook_event = WebhookSubscription(
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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )
    webhook_event = WebhookSubscription(
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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

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


@pytest.mark.parametrize(
    "base_url,subdomain,expected_output",
    [
        (
            "https://dev.azure.com/myorg",
            "vsaex",
            "https://vsaex.dev.azure.com/myorg",
        ),
        (
            "https://myorg.visualstudio.com",
            "vsaex",
            "https://myorg.vsaex.visualstudio.com",
        ),
        (
            "https://ado.local:8080/DefaultCollection",
            "vsaex",
            "https://ado.local:8080/DefaultCollection",
        ),
    ],
)
def test_format_service_url(
    base_url: str,
    subdomain: str,
    expected_output: str,
) -> None:
    client = AzureDevopsClient(base_url, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME)
    result = client._format_service_url(subdomain)
    assert result == expected_output


@pytest.mark.asyncio
async def test_get_repository_tree() -> None:
    """Test getting repository tree structure."""
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_get_paginated_by_top_and_continuation_token(
        url: str, additional_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        assert url.endswith(f"/_apis/git/repositories/{MOCK_REPOSITORY_ID}/items")
        assert additional_params is not None
        assert additional_params["recursionLevel"] == "none"

        if additional_params.get("scopePath", "/") != "/":
            yield []
            return

        yield [
            {
                "objectId": "abc123",
                "gitObjectType": "tree",
                "path": "/src/main",
            },
            {
                "objectId": "def456",
                "gitObjectType": "tree",
                "path": "/src/main/code",
            },
            {
                "objectId": "ghi789",
                "gitObjectType": "blob",
                "path": "/src/main/code/file.txt",
            },
        ]

    with patch.object(
        client,
        "_get_paginated_by_top_and_continuation_token",
        side_effect=mock_get_paginated_by_top_and_continuation_token,
    ):
        folders = []
        async for folder_batch in client.get_repository_tree(
            MOCK_REPOSITORY_ID, recursion_level="none"
        ):
            folders.extend(folder_batch)

        assert len(folders) == 2  # Only tree items
        assert all(folder["gitObjectType"] == "tree" for folder in folders)
        assert folders[0]["path"] == "/src/main"
        assert folders[1]["path"] == "/src/main/code"


@pytest.mark.asyncio
async def test_get_repository_tree_with_recursion() -> None:
    """Test getting repository tree structure with recursion."""
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    call_count = 0

    async def mock_get_paginated_by_top_and_continuation_token(
        url: str, additional_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        nonlocal call_count
        assert url.endswith(f"/_apis/git/repositories/{MOCK_REPOSITORY_ID}/items")
        assert additional_params is not None
        assert additional_params["recursionLevel"] == "full"

        yield [
            {
                "objectId": "abc123",
                "gitObjectType": "tree",
                "path": "/src",
            },
            {
                "objectId": "def456",
                "gitObjectType": "tree",
                "path": "/src/main",
            },
            {
                "objectId": "ghi789",
                "gitObjectType": "tree",
                "path": "/src/test",
            },
        ]

    with patch.object(
        client,
        "_get_paginated_by_top_and_continuation_token",
        side_effect=mock_get_paginated_by_top_and_continuation_token,
    ):
        folders = []
        async for folder_batch in client.get_repository_tree(
            MOCK_REPOSITORY_ID, recursion_level="full"
        ):
            folders.extend(folder_batch)

        assert len(folders) == 3
        paths = {folder["path"] for folder in folders}
        assert paths == {"/src", "/src/main", "/src/test"}


@pytest.mark.asyncio
async def test_get_repository_tree_will_skip_404(mock_event_context: MagicMock) -> None:
    """Test that get_repository_tree gracefully handles 404 errors."""
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_get_paginated_by_top_and_continuation_token(
        url: str, additional_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield []

    with patch.object(
        client,
        "_get_paginated_by_top_and_continuation_token",
        side_effect=mock_get_paginated_by_top_and_continuation_token,
    ):
        folders = []
        async for folder_batch in client.get_repository_tree(
            MOCK_REPOSITORY_ID, recursion_level="none"
        ):
            folders.extend(folder_batch)

        assert len(folders) == 0


@pytest.mark.asyncio
async def test_get_repository_tree_with_deep_path() -> None:
    """Test getting repository tree structure with deep path using **."""
    client = AzureDevopsClient(
        MOCK_ORG_URL, MOCK_PERSONAL_ACCESS_TOKEN, MOCK_AUTH_USERNAME
    )

    async def mock_get_paginated_by_top_and_continuation_token(
        url: str, additional_params: Optional[Dict[str, Any]] = None, **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        assert url.endswith(f"/_apis/git/repositories/{MOCK_REPOSITORY_ID}/items")
        assert additional_params is not None
        assert additional_params["recursionLevel"] == "full"
        assert additional_params["scopePath"] == "/src/**/*.py"

        yield [
            {
                "objectId": "abc123",
                "gitObjectType": "tree",
                "path": "/src/main",
            },
            {
                "objectId": "def456",
                "gitObjectType": "tree",
                "path": "/src/main/api",
            },
            {
                "objectId": "ghi789",
                "gitObjectType": "blob",
                "path": "/src/main/api/app.py",
            },
            {
                "objectId": "jkl012",
                "gitObjectType": "tree",
                "path": "/src/test",
            },
            {
                "objectId": "mno345",
                "gitObjectType": "blob",
                "path": "/src/test/test_app.py",
            },
            {
                "objectId": "pqr678",
                "gitObjectType": "blob",
                "path": "/src/main/utils.py",
            },
        ]

    with patch.object(
        client,
        "_get_paginated_by_top_and_continuation_token",
        side_effect=mock_get_paginated_by_top_and_continuation_token,
    ):
        folders = []
        async for folder_batch in client.get_repository_tree(
            MOCK_REPOSITORY_ID, path="/src/**/*.py", recursion_level="full"
        ):
            folders.extend(folder_batch)

        # Should only get tree (folder) items
        assert len(folders) == 3
        paths = {folder["path"] for folder in folders}
        assert paths == {"/src/main", "/src/main/api", "/src/test"}
        assert all(folder["gitObjectType"] == "tree" for folder in folders)


@pytest.mark.asyncio
async def test_process_folder_patterns(
    sample_folder_patterns: List[FolderPattern],
    mock_azure_client: AzureDevopsClient,
) -> None:
    async def mock_generate_repositories() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        repos_data = [
            {
                "name": "repo1",
                "id": "repo1-id",
                "project": {"name": "test-project", "id": "project-123"},
            },
            {
                "name": "repo2",
                "id": "repo2-id",
                "project": {"name": "test-project", "id": "project-123"},
            },
            {
                "name": "repo3",
                "id": "repo3-id",
                "project": {"name": "test-project", "id": "project-123"},
            },
        ]
        yield repos_data

    async def mock_get_repository_folders(
        repo_id: str, paths: List[str], **kwargs: Any
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        folders_data = []
        if repo_id == "repo1-id" and any(p.strip("/") == "src/main" for p in paths):
            folders_data = [
                {
                    "path": "src/main",
                    "gitObjectType": "tree",
                    "__repository": {
                        "id": "repo1-id",
                        "name": "repo1",
                        "project": {"name": "test-project", "id": "project-123"},
                    },
                    "__branch": "main",
                    "__pattern": "src/main",
                }
            ]
        elif repo_id == "repo2-id":
            if any(p.strip("/") == "src/main" for p in paths):
                folders_data = [
                    {
                        "path": "src/main",
                        "gitObjectType": "tree",
                        "__repository": {
                            "id": "repo2-id",
                            "name": "repo2",
                            "project": {"name": "test-project", "id": "project-123"},
                        },
                        "__branch": "main",
                        "__pattern": "src/main",
                    }
                ]
            elif any(p.strip("/") == "docs" for p in paths):
                folders_data = [
                    {
                        "path": "docs",
                        "gitObjectType": "tree",
                        "__repository": {
                            "id": "repo2-id",
                            "name": "repo2",
                            "project": {"name": "test-project", "id": "project-123"},
                        },
                        "__branch": "main",
                        "__pattern": "docs",
                    }
                ]
        elif repo_id == "repo3-id" and any(p.strip("/") == "docs" for p in paths):
            folders_data = [
                {
                    "path": "docs",
                    "gitObjectType": "tree",
                    "__repository": {
                        "id": "repo3-id",
                        "name": "repo3",
                        "project": {"name": "test-project", "id": "project-123"},
                    },
                    "__branch": "develop",
                    "__pattern": "docs",
                }
            ]

        if folders_data:
            yield folders_data

    async def mock_get_repository_by_name(
        project_name: str, repo_name: str
    ) -> Dict[str, Any]:
        return {
            "name": repo_name,
            "id": f"{repo_name}-id",
            "project": {"name": project_name, "id": "project-123"},
        }

    with (
        patch.object(
            mock_azure_client,
            "generate_repositories",
            side_effect=mock_generate_repositories,
        ),
        patch.object(
            mock_azure_client,
            "get_repository_folders",
            side_effect=mock_get_repository_folders,
        ),
        patch.object(
            mock_azure_client,
            "get_repository_by_name",
            side_effect=mock_get_repository_by_name,
        ),
    ):
        results: List[Dict[str, Any]] = []
        async for folders in mock_azure_client.process_folder_patterns(
            sample_folder_patterns,
            project_name="test-project",
        ):
            results.extend(folders)

        # Verify we got all expected folders
        assert len(results) == 4
        paths = {r["path"] for r in results}
        assert paths == {"src/main", "docs"}
        repos = {r["__repository"]["name"] for r in results}
        assert repos == {"repo1", "repo2", "repo3"}


@pytest.mark.asyncio
async def test_process_folder_patterns_empty_folders() -> None:
    """Test with empty folder patterns"""
    mock_client = AsyncMock(spec=AzureDevopsClient)
    results = []
    async for folders in mock_client.process_folder_patterns([]):
        results.extend(folders)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_process_folder_patterns_no_matching_repos() -> None:
    """Create patterns with non-existent repos"""
    patterns = [
        FolderPattern(
            path="/src",
            repos=[RepositoryBranchMapping(name="non-existent-repo", branch="main")],
        )
    ]

    mock_client = AsyncMock(spec=AzureDevopsClient)

    async def mock_generate_repositories() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        yield []

    mock_client.generate_repositories = mock_generate_repositories

    results = []
    async for folders in mock_client.process_folder_patterns(patterns):
        results.extend(folders)
    assert len(results) == 0


@pytest.mark.asyncio
async def test_process_folder_patterns_no_matching_folders() -> None:
    """Create patterns with valid repo but non-existent folders"""
    patterns = [
        FolderPattern(
            path="/non-existent-folder",
            repos=[RepositoryBranchMapping(name="repo1", branch="main")],
        )
    ]
    mock_client = AsyncMock(spec=AzureDevopsClient)

    async def mock_generate_repositories() -> (
        AsyncGenerator[List[Dict[str, Any]], None]
    ):
        yield [{"name": "repo1", "id": "repo1-id"}]

    async def mock_get_repository_folders(
        repo_id: str, paths: List[str]
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield []

    mock_client.generate_repositories = mock_generate_repositories
    mock_client.get_repository_folders = mock_get_repository_folders

    results = []
    async for folders in mock_client.process_folder_patterns(patterns):
        results.extend(folders)
    assert len(results) == 0
