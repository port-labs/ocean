import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

GITLAB_API_URL = os.getenv("GITLAB_API_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

async def fetch_merge_requests():
    url = f"{GITLAB_API_URL}/merge_requests"
    headers = {"Private-Token": GITLAB_TOKEN}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            print(f"Error fetching GitLab merge requests: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

async def resync_merge_requests(kind: str):
    merge_requests = await fetch_merge_requests()
    if merge_requests is None:
        print("No merge requests data to process.")
        return

    # Process the merge requests data
    print(f"Merge requests fetched: {merge_requests}")

    # Here, you would upsert entities based on the fetched data
    # Example: await upsert_merge_requests(merge_requests)
