import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

GITLAB_API_URL = os.getenv("GITLAB_API_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

async def fetch_issues():
    url = f"{GITLAB_API_URL}/issues"
    headers = {"Private-Token": GITLAB_TOKEN}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            print(f"Error fetching GitLab issues: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

async def resync_issues(kind: str):
    issues = await fetch_issues()
    if issues is None:
        print("No issues data to process.")
        return

    # Process the issues data
    print(f"Issues fetched: {issues}")

    # Here, you would upsert entities based on the fetched data
    # Example: await upsert_issues(issues)
