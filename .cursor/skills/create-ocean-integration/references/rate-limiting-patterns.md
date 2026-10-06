# Rate Limiting Patterns

## Preferred: Use aiolimiter

Use the `aiolimiter` library for rate limiting. Only implement custom rate limiters for special cases.

```python
from aiolimiter import AsyncLimiter

class BaseClient:
    def __init__(self, requests_per_second: float = 10):
        # 10 requests per second with burst of 1
        self.rate_limiter = AsyncLimiter(requests_per_second, 1)
    
    async def send_api_request(self, endpoint: str, ...) -> Dict[str, Any]:
        async with self.rate_limiter:
            response = await self._http_client.request(...)
            return response.json()
```

## Pattern 1: Overall Rate Limit (requests per time window)

```python
from aiolimiter import AsyncLimiter

# 100 requests per minute
rate_limiter = AsyncLimiter(100, 60)

# 1000 requests per hour
rate_limiter = AsyncLimiter(1000, 3600)

async def make_request():
    async with rate_limiter:
        # Request is rate-limited
        return await client.get(url)
```

## Pattern 2: Concurrent Limit (max simultaneous requests)

Use `asyncio.Semaphore` for concurrent limits (aiolimiter handles rate, not concurrency):

```python
import asyncio
from aiolimiter import AsyncLimiter

class RateLimitedClient:
    def __init__(self, requests_per_second: float = 10, max_concurrent: int = 5):
        self.rate_limiter = AsyncLimiter(requests_per_second, 1)
        self.semaphore = asyncio.Semaphore(max_concurrent)
    
    async def send_api_request(self, endpoint: str) -> Dict[str, Any]:
        async with self.semaphore:  # Limit concurrent requests
            async with self.rate_limiter:  # Limit request rate
                return await self._http_client.request(endpoint)
```

## Pattern 3: Different Limits per Endpoint Type

```python
from aiolimiter import AsyncLimiter

class MultiLimiterClient:
    def __init__(self):
        # REST: 100 req/min, GraphQL: 30 req/min
        self.rest_limiter = AsyncLimiter(100, 60)
        self.graphql_limiter = AsyncLimiter(30, 60)
    
    async def rest_request(self, endpoint: str) -> Dict[str, Any]:
        async with self.rest_limiter:
            return await self._http_client.get(endpoint)
    
    async def graphql_request(self, query: str) -> Dict[str, Any]:
        async with self.graphql_limiter:
            return await self._http_client.post("/graphql", json={"query": query})
```

## Custom Implementation: Header-Based Rate Limiter

Only use when API returns rate limit info in headers and you need to track remaining quota:

```python
from dataclasses import dataclass
from typing import Optional
import asyncio
import time

@dataclass
class RateLimitInfo:
    remaining: int
    reset_at: float  # Unix timestamp
    limit: int

class HeaderBasedRateLimiter:
    """Use only when you need to read rate limit headers from responses."""
    
    def __init__(self, max_concurrent: int = 10):
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.rate_limit_info: Optional[RateLimitInfo] = None
        self._lock = asyncio.Lock()
    
    async def __aenter__(self):
        await self.semaphore.acquire()
        
        async with self._lock:
            if self.rate_limit_info and self.rate_limit_info.remaining <= 1:
                sleep_time = self.rate_limit_info.reset_at - time.time()
                if sleep_time > 0:
                    logger.info(f"Rate limit near, sleeping {sleep_time}s")
                    await asyncio.sleep(sleep_time)
    
    async def __aexit__(self, *args):
        self.semaphore.release()
    
    def on_response(self, headers: Dict[str, str]) -> None:
        remaining = headers.get("X-RateLimit-Remaining")
        reset = headers.get("X-RateLimit-Reset")
        limit = headers.get("X-RateLimit-Limit")
        
        if remaining and reset:
            self.rate_limit_info = RateLimitInfo(
                remaining=int(remaining),
                reset_at=float(reset),
                limit=int(limit) if limit else 0,
            )
```

## Decision Matrix

| Scenario | Implementation |
|----------|----------------|
| Known requests/second or requests/minute limit | `aiolimiter.AsyncLimiter` |
| Concurrent request limit only | `asyncio.Semaphore` |
| Both rate and concurrent limits | Combine `AsyncLimiter` + `Semaphore` |
| Different limits per endpoint type | Multiple `AsyncLimiter` instances |
| API returns rate limit headers to track | Custom header-based limiter |
| No documented limits | Use Ocean defaults, add if 429s occur |
