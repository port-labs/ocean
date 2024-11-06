import pytest
import logging
from client import GitLabHandler
from unittest.mock import AsyncMock, patch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Sample data for testing
GROUP_DATA = [{"id": 1, "name": "Group 1", "web_url": "https://gitlab.com/group1", "description": "Test group", "visibility": "public"}]
PROJECT_DATA = [{"id": 1, "name": "Project 1", "web_url": "https://gitlab.com/project1", "description": "Test project", "namespace": {"full_path": "namespace1"}}]
MERGE_REQUEST_DATA = [{"id": 1, "title": "Merge Request 1", "state": "opened", "author": {"username": "author1"}, "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z", "merged_at": None, "web_url": "https://gitlab.com/mr1", "reviewers": [{"username": "reviewer1"}]}]
ISSUE_DATA = [{"id": 1, "title": "Issue 1", "state": "opened", "author": {"username": "author1"}, "created_at": "2023-01-01T00:00:00Z", "updated_at": "2023-01-02T00:00:00Z", "closed_at": None, "web_url": "https://gitlab.com/issue1", "labels": ["bug", "urgent"]}]

@pytest.fixture
def gitlab_handler():
    handler = GitLabHandler()
    handler._rate_limited_request = AsyncMock()  # Mock API call method
    return handler

@pytest.mark.asyncio
async def test_fetch_groups(gitlab_handler):
    logger.info("Starting test_fetch_groups")
    gitlab_handler._rate_limited_request.return_value = GROUP_DATA
    result = await gitlab_handler.fetch_groups()
    assert result == [{"identifier": 1, "name": "Group 1", "url": "https://gitlab.com/group1", "description": "Test group", "visibility": "public"}]
    gitlab_handler._rate_limited_request.assert_called_once_with("/groups")
    logger.info("Completed test_fetch_groups successfully")

@pytest.mark.asyncio
async def test_fetch_projects(gitlab_handler):
    logger.info("Starting test_fetch_projects")
    gitlab_handler._rate_limited_request.return_value = PROJECT_DATA
    result = await gitlab_handler.fetch_projects()
    assert result == [{"identifier": 1, "name": "Project 1", "url": "https://gitlab.com/project1", "description": "Test project", "namespace": "namespace1"}]
    gitlab_handler._rate_limited_request.assert_called_once_with("/projects", {"per_page": gitlab_handler.rate_limit})
    logger.info("Completed test_fetch_projects successfully")

@pytest.mark.asyncio
async def test_fetch_merge_requests(gitlab_handler):
    logger.info("Starting test_fetch_merge_requests")
    gitlab_handler._rate_limited_request.return_value = MERGE_REQUEST_DATA
    result = await gitlab_handler.fetch_merge_requests()
    assert result == [{"identifier": 1, "title": "Merge Request 1", "status": "opened", "author": "author1", "createdAt": "2023-01-01T00:00:00Z", "updatedAt": "2023-01-02T00:00:00Z", "mergedAt": None, "link": "https://gitlab.com/mr1", "reviewers": ["reviewer1"]}]
    gitlab_handler._rate_limited_request.assert_called_once_with("/merge_requests", {"scope": "all", "per_page": gitlab_handler.rate_limit})
    logger.info("Completed test_fetch_merge_requests successfully")

@pytest.mark.asyncio
async def test_fetch_issues(gitlab_handler):
    logger.info("Starting test_fetch_issues")
    gitlab_handler._rate_limited_request.return_value = ISSUE_DATA
    result = await gitlab_handler.fetch_issues()
    assert result == [{"identifier": 1, "title": "Issue 1", "status": "opened", "author": "author1", "createdAt": "2023-01-01T00:00:00Z", "updatedAt": "2023-01-02T00:00:00Z", "closedAt": None, "link": "https://gitlab.com/issue1", "labels": ["bug", "urgent"]}]
    gitlab_handler._rate_limited_request.assert_called_once_with("/issues", {"scope": "all", "per_page": gitlab_handler.rate_limit})
    logger.info("Completed test_fetch_issues successfully")
