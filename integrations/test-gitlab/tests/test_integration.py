import asyncio
import logging

from client import GitLabHandler

# Initialize logging
logging.basicConfig(level=logging.INFO)

# Instantiate GitLabHandler
gitlab_handler = GitLabHandler()

async def test_fetch_groups():
    """Test fetching groups."""
    try:
        groups = await gitlab_handler.fetch_groups()
        print("Fetched Groups:", groups)
    except Exception as e:
        logging.error(f"Error fetching groups: {e}")

async def test_fetch_projects():
    """Test fetching projects."""
    try:
        projects = await gitlab_handler.fetch_projects()
        print("Fetched Projects:", projects)
    except Exception as e:
        logging.error(f"Error fetching projects: {e}")

async def test_fetch_merge_requests():
    """Test fetching merge requests."""
    try:
        merge_requests = await gitlab_handler.fetch_merge_requests()
        print("Fetched Merge Requests:", merge_requests)
    except Exception as e:
        logging.error(f"Error fetching merge requests: {e}")

async def test_fetch_issues():
    """Test fetching issues."""
    try:
        issues = await gitlab_handler.fetch_issues()
        print("Fetched Issues:", issues)
    except Exception as e:
        logging.error(f"Error fetching issues: {e}")

# Run all tests
async def main():
    await test_fetch_groups()
    await test_fetch_projects()
    await test_fetch_merge_requests()
    await test_fetch_issues()

# Execute the tests
asyncio.run(main())
