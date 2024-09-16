import aiohttp
import os
from dotenv import load_dotenv

load_dotenv()

GITLAB_API_URL = os.getenv("GITLAB_API_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

async def fetch_groups():
    url = f"{GITLAB_API_URL}/groups"
    headers = {"Private-Token": GITLAB_TOKEN}

    async with aiohttp.ClientSession() as session:
        try:
            async with session.get(url, headers=headers) as response:
                response.raise_for_status()
                return await response.json()
        except aiohttp.ClientResponseError as e:
            print(f"Error fetching GitLab groups: {e}")
            return None
        except Exception as e:
            print(f"Unexpected error: {e}")
            return None

async def resync_group(kind: str):
    groups = await fetch_groups()
    if groups is None:
        print("No groups data to process.")
        return

    # Process the groups data
    print(f"Groups fetched: {groups}")

    # Here, you would upsert entities based on the fetched data
    # Example: await upsert_groups(groups)
