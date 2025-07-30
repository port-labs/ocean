import asyncio
import functools

def retry_with_backoff(func):
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        retries = 3
        for attempt in range(retries):
            try:
                return await func(*args, **kwargs)
            except Exception as e:
                if "rate limit" in str(e).lower():
                    wait_time = 2 ** attempt
                    print(f"Rate limited. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise
        raise RuntimeError("Rate limit exceeded after retries")
    return wrapper
