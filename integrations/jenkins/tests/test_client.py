import pytest
from unittest.mock import AsyncMock, patch
from client import JenkinsClient
from typing import Any, AsyncGenerator, Dict, List


@pytest.mark.asyncio
@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    new_callable=AsyncMock,
)
@patch("port_ocean.utils.async_http.OceanAsyncClient", new_callable=AsyncMock)
async def test_get_stages(
    mock_ocean_client: AsyncMock, mock_integration_config: AsyncMock
) -> None:
    # Mock integration config
    mock_integration_config.return_value = {
        "jenkins_host": "http://localhost:8080",
        "jenkins_user": "hpal[REDACTED]",
        "jenkins_token": "11b053[REDACTED]",
    }

    # Mock data
    job_url = "http://jenkins.example.com/job/test-job/"
    build_url = "http://jenkins.example.com/job/test-job/1/"
    mock_stages = [
        {
            "_links": {
                "self": {"href": "/job/test-job/1/execution/node/6/wfapi/describe"}
            },
            "id": "6",
            "name": "Declarative: Checkout SCM",
            "execNode": "",
            "status": "SUCCESS",
            "startTimeMillis": 1717068226152,
            "durationMillis": 1173,
            "pauseDurationMillis": 0,
        },
        {
            "_links": {
                "self": {"href": "/job/test-job/1/execution/node/17/wfapi/describe"}
            },
            "id": "17",
            "name": "Declarative: Post Actions",
            "execNode": "",
            "status": "SUCCESS",
            "startTimeMillis": 1717068227381,
            "durationMillis": 25,
            "pauseDurationMillis": 0,
        },
    ]

    # Create a JenkinsClient instance
    with patch("client.http_async_client", new=mock_ocean_client):
        client = JenkinsClient("http://jenkins.example.com", "user", "token")

    # Mock the necessary methods
    async def mock_get_job_builds(
        job_url: str,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        yield [{"url": build_url}]

    with (
        patch.object(
            client, "_get_job_builds", side_effect=mock_get_job_builds
        ) as mock_get_job_builds,
        patch.object(
            client, "_get_build_stages", new_callable=AsyncMock
        ) as mock_get_build_stages,
    ):

        # Set up the mock returns
        mock_get_build_stages.return_value = mock_stages

        # Call the method and collect results
        stages = []
        async for stage_batch in client.get_stages(job_url):
            stages.extend(stage_batch)

        # Assertions
        assert stages == mock_stages
        mock_get_job_builds.assert_called_once_with(job_url)
        mock_get_build_stages.assert_called_once_with(build_url)


@pytest.mark.asyncio
@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    new_callable=AsyncMock,
)
@patch("port_ocean.utils.async_http.OceanAsyncClient", new_callable=AsyncMock)
async def test_get_stages_nested_jobs(
    mock_ocean_client: AsyncMock, mock_integration_config: AsyncMock
) -> None:
    # Mock integration config
    mock_integration_config.return_value = {
        "jenkins_host": "http://localhost:8080",
        "jenkins_user": "hpal[REDACTED]",
        "jenkins_token": "11b053[REDACTED]",
    }

    # Mock data
    parent_job_url = "http://jenkins.example.com/job/parent-job/"
    child_job_url = "http://jenkins.example.com/job/parent-job/job/child-job/"
    build_url = "http://jenkins.example.com/job/parent-job/job/child-job/1/"
    mock_stages = [
        {
            "id": "6",
            "name": "Build",
            "status": "SUCCESS",
            "startTimeMillis": 1717068226152,
            "durationMillis": 1173,
            "pauseDurationMillis": 0,
        },
        {
            "id": "17",
            "name": "Test",
            "status": "SUCCESS",
            "startTimeMillis": 1717068227381,
            "durationMillis": 25,
            "pauseDurationMillis": 0,
        },
    ]

    # Create a JenkinsClient instance
    with patch("client.http_async_client", new=mock_ocean_client):
        client = JenkinsClient("http://jenkins.example.com", "user", "token")

    # Mock the necessary methods
    async def mock_get_single_resource(resource_url: str) -> Dict[str, Any]:
        if resource_url == parent_job_url:
            return {"buildable": False, "jobs": [{"url": child_job_url}]}
        elif resource_url == child_job_url:
            return {"buildable": True, "builds": [{"url": build_url}]}
        else:
            return {"buildable": False}

    async def mock_get_paginated_resources(
        resource: str, parent_job: str | None = None
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        if parent_job is None:
            yield [
                {
                    "url": child_job_url,
                    "buildable": False,
                    "jobs": [{"url": child_job_url}],
                }
            ]
        else:
            yield [
                {
                    "url": child_job_url,
                    "buildable": True,
                    "builds": [{"url": build_url}],
                }
            ]

    with (
        patch.object(
            client, "get_single_resource", side_effect=mock_get_single_resource
        ) as mock_get_single_resource,
        patch.object(
            client, "_get_paginated_resources", side_effect=mock_get_paginated_resources
        ) as mock_get_paginated_resources,
        patch.object(
            client, "_get_build_stages", new_callable=AsyncMock
        ) as mock_get_build_stages,
    ):

        # Set up the mock returns
        mock_get_build_stages.return_value = mock_stages

        # Call the method and collect results
        stages = []
        async for stage_batch in client.get_stages(parent_job_url):
            stages.extend(stage_batch)

        # Assertions
        assert stages == mock_stages
        mock_get_single_resource.assert_called_with(parent_job_url)
        mock_get_paginated_resources.assert_called()
        mock_get_build_stages.assert_called_once_with(build_url)


@pytest.mark.asyncio
@patch(
    "port_ocean.context.ocean.PortOceanContext.integration_config",
    new_callable=AsyncMock,
)
@patch("port_ocean.utils.async_http.OceanAsyncClient", new_callable=AsyncMock)
async def test_jenkins_client_url_no_trailing_slashes(
    mock_ocean_client: AsyncMock, mock_integration_config: AsyncMock
) -> None:
    mock_integration_config.return_value = {
        "jenkins_host": "http://localhost:8080",
        "jenkins_user": "user",
        "jenkins_token": "token",
    }

    test_urls = [
        "http://jenkins.example.com",
        "http://jenkins.example.com/",
        "http://jenkins.example.com//",
    ]

    with patch("client.http_async_client", new=mock_ocean_client):
        for url in test_urls:
            client = JenkinsClient(url, "user", "token")
            assert client.jenkins_base_url == "http://jenkins.example.com"
