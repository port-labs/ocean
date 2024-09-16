import os
import aiohttp
from typing import Any, List
from dotenv import load_dotenv

load_dotenv()

GITLAB_API_URL = os.getenv("GITLAB_API_URL")
GITLAB_TOKEN = os.getenv("GITLAB_TOKEN")

async def fetch_gitlab_data(endpoint: str) -> List[dict[Any, Any]]:
    headers = {'Authorization': f'Bearer {GITLAB_TOKEN}'}
    async with aiohttp.ClientSession(headers=headers) as session:
        async with session.get(f"{GITLAB_API_URL}/{endpoint}") as response:
            return await response.json()