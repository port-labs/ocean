---
title: Implementing an API Client
sidebar_label: 🔗 Implementing an API Client
sidebar_position: 3
---

# 🔗 Implementing an API Client

## Introduction

When building an integration for Ocean, you'll need an API client to interact with your third-party service. Let's explore how to build one using both Jira and Octopus Deploy as our examples. These integrations demonstrate different approaches to common challenges, giving you flexibility in how you implement your own integration.

Key concepts we'll cover:
- Authentication handling: Securely connect to your service (Basic Auth, OAuth, API Keys)
- Data retrieval patterns: Efficiently fetch and process data with pagination
- Webhook configuration: Set up real-time updates
- Rate limiting and pagination: Handle large datasets safely


## Client Structure

Let's create our client classes! This is where the magic happens - it's the core of our integration that handles all API interactions. We'll look at both Jira and Octopus implementations to show different approaches:

```python
# Jira Client
class JiraClient(OAuthClient):
    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        super().__init__()
        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        # If the Jira URL is directing to api.atlassian.com, we use OAuth2 Bearer Auth
        if self.is_oauth_host():
            self.jira_api_auth = self._get_bearer()
            self.webhooks_url = f"{self.jira_rest_url}/api/3/webhook"
        else:
            self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)
            self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

# Octopus Client
class OctopusClient:
    def __init__(self, server_url: str, octopus_api_key: str) -> None:
        self.octopus_url = f"{server_url.rstrip('/')}/api/"
        self.api_auth_header = {"X-Octopus-ApiKey": octopus_api_key}
        self.client = http_async_client
        self.client.timeout = Timeout(CLIENT_TIMEOUT)
        self.client.headers.update(self.api_auth_header)
```

Notice how each client handles authentication differently:
- Jira supports both OAuth and Basic Auth
- Octopus uses a simple API key in headers
- Both use the same underlying HTTP client with different configurations

## Using Ocean's HTTP Client

When building an Ocean integration, we strongly recommend using `http_async_client` from Ocean's utils instead of creating your own HTTP client or using libraries like `requests` or `httpx` directly. Here's why:

1. **Performance Optimization**:
   - The client is pre-configured with optimal settings for Ocean integrations
   - Includes built-in connection pooling and keep-alive
   - Optimized for async operations

2. **Built-in Features**:
   - Automatic retry mechanism with exponential backoff
   - Rate limiting support
   - Proper timeout handling
   - Consistent error handling

3. **Framework Integration**:
   - Seamlessly integrates with Ocean's logging and monitoring
   - Works with Ocean's authentication mechanisms
   - Supports Ocean's configuration system

4. **Maintenance Benefits**:
   - Centralized updates and improvements
   - Consistent behavior across all integrations
   - Reduced code duplication

To use the client, simply import it from Ocean's utils:

```python
from port_ocean.utils import http_async_client

# Use it in your client class
class MyClient:
    def __init__(self):
        self.client = http_async_client
        # Configure as needed
        self.client.timeout = Timeout(30)
```

## API Request Handling

When building an API client, it's crucial to have a centralized method for handling all API requests. This approach provides several benefits:
- Consistent error handling across all requests
- Centralized rate limiting and retry logic
- Unified logging and monitoring
- Easier maintenance and updates

Let's look at how Jira implements this pattern, it is important to note that the choice of approach should be driven solely by the API's requirements and the integration's needs.

```python
    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method, url=url, params=params, json=json
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:  # Rate limit
                retry_after = int(e.response.headers.get("Retry-After", "60"))
                await asyncio.sleep(retry_after)
                return await self._send_api_request(method, url, params, json)
            raise
```

Key aspects of this implementation:
1. **Concurrency Control**: Uses a semaphore to limit concurrent requests
2. **Error Handling**: Catches and processes HTTP errors
3. **Rate Limiting**: Implements automatic retry with backoff for rate limits
4. **Response Processing**: Automatically parses JSON responses

Now, let's see how Octopus handles API requests:

```python
    async def _send_api_request(
        self,
        endpoint: str,
        params: Optional[dict[str, Any]] = None,
        json_data: Optional[dict[str, Any]] = None,
        method: str = "GET",
    ) -> Any:
        """Send a request to the Octopus Deploy API."""
        url = f"{self.octopus_url}{endpoint}"
        response = await self.client.request(
            url=url,
            method=method,
            headers=self.api_auth_header,
            params=params,
            json=json_data,
        )
        try:
            response.raise_for_status()
        except HTTPStatusError as e:
            logger.error(
                f"Got HTTP error to url: {url} with status code: {e.response.status_code} and response text: {e.response.text}"
            )
            raise
        return response.json()
```

The Octopus implementation shows a simpler approach:
1. **URL Construction**: Builds the full URL from base URL and endpoint
2. **Header Management**: Automatically includes authentication headers
3. **Error Logging**: Provides detailed error information for debugging
4. **Response Handling**: Similar JSON parsing but with different error handling

Both implementations demonstrate good practices for API request handling, but they're tailored to their specific needs:
- Jira's implementation focuses on rate limiting and retries
- Octopus's implementation emphasizes logging and error details

## Data Retrieval

When implementing data retrieval in your integration, you have two main approaches: specific implementations for each resource type or a generic implementation that can handle multiple resource types. Let's explore both approaches using Jira and Octopus as examples.

The Octopus implementation demonstrates a more generic and extensible approach, which makes it easier to add support for new resource kinds without writing additional code. However, it's important to note that the best approach depends on your API's characteristics and requirements.

Let's first look at Jira's pagination helper and the `get_paginated_<kind>` methods, which fits the Jira API's requirements:

```python
    async def _get_paginated_data(
        self,
        url: str,
        extract_key: str | None = None,
        initial_params: dict[str, Any] | None = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        params = initial_params or {}
        params |= self._generate_base_req_params()

        start_at = 0
        while True:
            params["startAt"] = start_at
            response_data = await self._send_api_request("GET", url, params=params)
            items = response_data.get(extract_key, []) if extract_key else response_data

            if not items:
                break

            yield items

            start_at += len(items)

            if "total" in response_data and start_at >= response_data["total"]:
                break


    async def get_paginated_projects(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Jira")
        async for projects in self._get_paginated_data(
            f"{self.api_url}/project/search", "values", initial_params=params
        ):
            yield projects
```

Now, let's look at Octopus's more generic approach:

```python
    async def get_paginated_resources(
        self,
        kind: str,
        params: Optional[dict[str, Any]] = None,
        path_parameter: Optional[str] = None,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Fetch paginated data from the Octopus Deploy API."""
        endpoint = f"{path_parameter}/{kind}s" if path_parameter else f"{kind}s"
        if params is None:
            params = {}
        params["skip"] = 0
        params["take"] = PAGE_SIZE
        page = 0
        while True:
            response = await self._send_api_request(endpoint, params=params)
            items = response.get("Items", [])
            last_page = response.get("LastPageNumber", 0)
            yield items
            if page >= last_page:
                break
            if kind in KINDS_WITH_LIMITATION and params["skip"] >= MAX_ITEMS_LIMITATION:
                logger.warning(
                    f"Reached the limit of {MAX_ITEMS_LIMITATION} {kind}s. Skipping the rest of the {kind}s."
                )
                break
            params["skip"] += PAGE_SIZE
            page += 1
```

The key differences between these approaches:

1. **Generic vs. Specific**:
   - Octopus's implementation is more generic and can handle any resource kind
   - Jira's implementation is tailored to Jira's specific pagination model
   - Both approaches are valid, but the generic approach requires less code when adding new resources

2. **Extensibility**:
   - With Octopus's approach, adding a new resource kind only requires calling `get_paginated_resources` with the new kind
   - Jira's approach requires creating a new method for each resource type
   - The generic approach makes it easier to maintain and extend the integration

3. **API Compatibility**:
   - Jira's implementation is optimized for Jira's offset-based pagination
   - Octopus's implementation works well with Octopus's skip/take pagination
   - The best approach depends on your API's pagination model


:::tip Best Practice for API Client
When designing your API client, consider these factors:
1. Always use `http_async_client` from Ocean's utils for making API requests. This ensures your integration benefits from Ocean's optimizations and maintains consistency with other integrations.
2. If your API has a consistent pagination model across all endpoints, a generic approach like Octopus's can save you time and reduce code duplication
3. If your API has different pagination models or special requirements for different resources, a more specific approach like Jira's might be more appropriate
4. Always prioritize API compatibility and reliability over code reusability
5. Consider using a generic approach with specific overrides when needed
6. Remember to add unit tests for your client
:::

## Webhook Configuration

Let's make our integration real-time! Webhooks notify the integration immediately when something changes in the third-party service and this helps us to keep the data in the catalog up to date. To set up a webhook, we need to add methods to the client to get the webhooks and create them if they don't exist. The following example shows how to set up a webhook using Jira as an example:

Key concepts for webhook implementation:
1. **Permission Checking**: Verify if the integration has the necessary permissions to create webhooks if api supports it
2. **Webhook Management**: Check for existing webhooks to avoid duplicates and handle webhook creation/updates
3. **Error Handling**: Proper logging and error handling for webhook operations
4. **Event Filtering**: Configure which events should trigger the webhook

Here's how Jira implements these concepts:

```python
    async def has_webhook_permission(self) -> bool:
        logger.info(f"Checking webhook permissions for Jira instance: {self.jira_url}")
        response = await self._send_api_request(
            method="GET",
            url=f"{self.api_url}/mypermissions",
            params={"permissions": "ADMINISTER"},
        )
        has_permission = response["permissions"]["ADMINISTER"]["havePermission"]

        return has_permission

    async def create_webhooks(self, app_host: str) -> None:
        """Create webhooks if the user has permission."""
        if not await self.has_webhook_permission():
            logger.warning(
                f"Cannot create webhooks for {self.jira_url}: Ensure the token has Jira Administrator rights."
            )
            return

        await self._create_events_webhook(app_host)

    async def _create_events_webhook(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhooks = await self._send_api_request("GET", url=self.webhooks_url)

        for webhook in webhooks:
            if webhook.get("url") == webhook_target_app_host:
                logger.info("Ocean real time reporting webhook already exists")
                return

        body = {
            "name": f"{ocean.config.integration.identifier}-{WEBHOOK_NAME}",
            "url": webhook_target_app_host,
            "events": WEBHOOK_EVENTS,
        }

        await self._send_api_request("POST", self.webhooks_url, json=body)
        logger.info("Ocean real time reporting webhook created")
```

:::tip Best Practice
When implementing webhooks:
1. Always check permissions before attempting to create webhooks
2. Implement proper error handling and logging
3. Configure event filtering to minimize unnecessary webhook calls
4. Use descriptive names for webhooks to make them easily identifiable
:::



:::info Want to see more?
Check out the full Jira client implementation [here](https://github.com/port-labs/ocean/blob/main/integrations/jira/jira/client.py) for more examples and inspiration!
:::
