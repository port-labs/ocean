import asyncio
import gitlab

class AsyncFetcher:
    @staticmethod
    async def get_gitlab_client(url: str, token: str) -> gitlab.Gitlab:
        return gitlab.Gitlab(url, private_token=token, api_version="4")

    @staticmethod
    async def fetch_single(fetch_method, *args, **kwargs):
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, fetch_method, *args, **kwargs)