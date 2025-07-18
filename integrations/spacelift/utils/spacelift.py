from integrations.spacelift.resources.stacks import StacksFetcher

async def fetch_stacks():
    fetcher = StacksFetcher()
    results = []
    async for stack in fetcher.fetch():
        results.append(stack)
    return results
