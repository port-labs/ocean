---
sidebar_position: 2
---


# 🔗 Implementing an API Client

## Introduction

When building a Jira integration for Ocean, the first step is to create an API client that:

- **Authenticates with Jira:** Use Basic Authentication or, optionally, OAuth tokens.
- **Retrieves data from Jira:** Sends authenticated requests to fetch API resources. This guide focuses on projects and issues, though support can be extended to include additional resources like users, teams, or boards as needed.
- **Configures webhooks:** Set up webhooks to report real-time updates, such as new issues or changes to projects, to Ocean.

In this guide, we’ll walk through the process of creating a `JiraClient` class that encapsulates all the Jira API logic. This class will be used to interact with Jira’s REST API, fetch data, and set up webhooks. We are concerned with the following API endpoints:

- [Jira Project API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-projects/#api-rest-api-3-project-search-get)
- [Jira Issue API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-issue-search/#api-rest-api-3-search-get)
- [Jira Webhooks API](https://developer.atlassian.com/cloud/jira/platform/rest/v3/api-group-webhooks/#api-group-webhooks)

## Create the `client.py` File

Create a `client.py` (or similarly named file) in your Jira integration directory. For example:

```console
$ mkdir jira && touch jira/client.py
```

This file will contain the `JiraClient` class, which would encapsulate all the logic needed to interact with Jira's API. Note that, the `client.py` file is created in another `jira` directory which is inside the Jira integration.

## The `JiraClient` Constructor

In the constructor, we need to handle:

- **Jira URLs**: the base Jira URL (could be on Atlassian’s cloud or self-hosted).
- **Auth details**: either Basic Auth or OAuth-based Bearer token.
- **Concurrent Requests**: We’ll use an `asyncio.Semaphore` to limit the number of concurrent requests to avoid performance pitfalls or hitting Jira’s concurrency limits.

Below, we implement the class constructor. Notice how we set up the base URLs and choose the authentication scheme depending on whether `api.atlassian.com` is detected. We assume that the presence of `api.atlassian.com` means this is an Oauth flow.


<details>

<summary><b>GitHub Client constructor (Click to expand)</b></summary>

```python showLineNumbers
import asyncio
import uuid
from typing import Any, AsyncGenerator, Generator

import httpx
from httpx import Auth, BasicAuth, Request, Response, Timeout
from loguru import logger

# ocean-related imports
from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
MAX_CONCURRENT_REQUESTS = 10

WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "project_created",
    "project_updated",
    "project_deleted",
    "project_soft_deleted",
    "project_restored_deleted",
    "project_archived",
    "project_restored_archived",
]

OAUTH2_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
]

class BearerAuth(Auth):
    """
    Simple custom Bearer token handler for OAuth.
    """
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request

class JiraClient(OAuthClient):
    jira_api_auth: Auth

    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        # Initialize the OAuthClient base class from port_ocean
        super().__init__()

        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        # Distinguish between OAuth (bearer) or Basic Auth:
        if self.is_oauth_host():
            self.jira_api_auth = self._get_bearer()
            self.webhooks_url = f"{self.jira_rest_url}/api/3/webhook"
        else:
            self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)
            self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        # Additional endpoints relevant to Jira
        self.api_url = f"{self.jira_rest_url}/api/3"
        self.teams_base_url = f"{self.jira_url}/gateway/api/public/teams/v1/org"

        # Configure httpx client
        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)

        # Use a semaphore to limit concurrent requests
        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def is_oauth_host(self) -> bool:
        """
        If the Jira instance is at 'api.atlassian.com',
        treat it as an OAuth-based host.
        """
        return "api.atlassian.com" in self.jira_url

    def _get_bearer(self) -> BearerAuth:
        """
        Returns a BearerAuth if we have a valid external access token,
        otherwise falls back to using the class's jira_token attribute.
        """
        try:
            return BearerAuth(self.external_access_token)
        except ValueError:
            return BearerAuth(self.jira_token)
```

</details>

A few things to take note of:

- **self.client**: Since Ocean integrations are developed with speed and performance in mind, we will be using Python's async features which naturally leads us to use a robust async http client, [httpx](https://www.python-httpx.org/). Fortunately, the `httpx` library is already included in the Ocean framework with helper features such as exponential backoff retry mechanism and other sensible defaults so we don't need to install or configure it separately.
- **`super().__init__()`**: We extend `OAuthClient` to leverage built-in capabilities for OAuth tokens.
- **`_semaphore`**: Limits concurrency to `MAX_CONCURRENT_REQUESTS`.

:::tip Special concurrency or rate-limit guidelines
If there are special concurrency or rate-limit guidelines from the third-party API (e.g., cloud vs. on-prem)? You might want to tweak the use of semaphore or add additional retry logic.

:::

## Handling Basic Auth vs. OAuth2

As shown in the constructor, we automatically detect if the Jira URL contains `"api.atlassian.com"`. If it does, we assume **OAuth**. Otherwise, we default to **BasicAuth**.

- **OAuth** scenario: We rely on `BearerAuth`, which is a simple custom class that sets the `Authorization` header with a Bearer token.
- **BasicAuth** scenario: We pass the user’s **email** and a **token** (often an API token from Jira).

## Sending API Requests (`_send_api_request`)

Like in the GitHub example, we want a single utility method that **all** request-making functions can call. This method handles:

1. **Concurrency**: by awaiting `self._semaphore`.
2. **Exceptions**: logging errors and re-raising them so we can handle them upstream.
3. **HTTP status checks**: raising for non-2xx responses (via `response.raise_for_status()`).
4. **Rate-limiting or throttling**: you could add additional logic if Jira imposes rate limits. In the snippet below, we show a small `_handle_rate_limit` method to check for `429` responses.


<details>

<summary><b>GitHub Client `_send_api_request` method (Click to expand)</b></summary>

```python showLineNumbers
    async def _handle_rate_limit(self, response: Response) -> None:
        if response.status_code == 429:
            logger.warning(
                f"Jira API rate limit reached. Waiting for {response.headers['Retry-After']} seconds."
            )
            await asyncio.sleep(int(response.headers["Retry-After"]))

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            # If we hit a 429, handle it
            await self._handle_rate_limit(e.response)
            logger.error(
                f"Jira API request failed with status {e.response.status_code}: {method} {url}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Jira API: {method} {url} - {str(e)}")
            raise
```

</details>

## Pagination Helpers (`_get_paginated_data`)

Jira’s APIs use two kinds of pagination:

- **Offset-based**: A typical pattern where requests have parameters like `startAt` and `maxResults`.
- **Cursor-based**: Some endpoints (like Teams) use a `cursor` param for subsequent pages.

Since we are concerned with projects and teams which uses the offset pagination method, we can implement a helper method for that:

### `_get_paginated_data`

- Accepts an `extract_key` (e.g., `"values"` or `"issues"`) to pick which part of the response we’re interested in.
- Yields data in **batches** (an async generator).
- Updates `startAt` each iteration until we reach `total`.


<details>

<summary><b>GitHub Client `_get_paginated_data` method (Click to expand)</b></summary>


```python showLineNumbers
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

            # Stop if we've reached the total
            if "total" in response_data and start_at >= response_data["total"]:
                break

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = PAGE_SIZE, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

```

</details>

This approach ensures that other methods—like fetching projects or issues—can just call `_get_paginated_data(...)` without worrying about the iteration details.

## Retrieving Projects

We want to **ingest Jira projects**. The method `get_paginated_projects` handles it by:

- Logging an informational message.
- Calling `_get_paginated_data` with `url=f"{self.api_url}/project/search"` and `extract_key="values"` (since Jira’s response nest projects in `["values"]`).
- Yielding each page’s worth of projects.


<details>

<summary><b>GitHub Client `get_paginated_projects` method (Click to expand)</b></summary>


```python showLineNumbers
    async def get_paginated_projects(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Jira")
        async for projects in self._get_paginated_data(
            f"{self.api_url}/project/search", "values", initial_params=params
        ):
            yield projects

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        return await self._send_api_request(
            "GET", f"{self.api_url}/project/{project_key}"
        )

```

</details>

- **`get_paginated_projects`** is an **async generator**, so you can `async for batch in get_paginated_projects(): ...` to process and send them to Ocean as they arrive.
- **`get\_single\_projects`** is a simpler case for retrieving one project by key. We will be needing this method when implementing webhooks.


## Retrieving Issues

Similarly, to **ingest Jira issues**, we provide:

- **`get_paginated_issues`**: Yields issues in pages.
- **`get_single_issue`**: Retrieves an individual issue by key.


<details>

<summary><b>GitHub Client `get_paginated_issues` and `get_single_issue` methods (Click to expand)</b></summary>

```python showLineNumbers
    async def get_single_issue(self, issue_key: str) -> dict[str, Any]:
        return await self._send_api_request("GET", f"{self.api_url}/issue/{issue_key}")

    async def get_paginated_issues(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Jira")
        params = params or {}
        if "jql" in params:
            logger.info(f"Using JQL filter: {params['jql']}")

        async for issues in self._get_paginated_data(
            f"{self.api_url}/search", "issues", initial_params=params
        ):
            yield issues
```

</details>

- `params["jql"]`: This is used when we would like to specify criteria for retrieving issues based on the user's preference.

## Implementing Real-Time Updates With Webhooks

Keeping data updated in real-time in Ocean uses webhooks primarily. Third-party APIs with webhook support ensures this is possible. The `JiraClient` snippet includes `create_webhooks`, `_create_events_webhook`, and `_create_events_webhook_oauth` to handle it.

### OAuth-Based Webhooks

If the Jira instance is Atlassian Cloud (`api.atlassian.com`), we call `_create_events_webhook_oauth`. This method:

1. Checks if any webhook is already registered (GET call).
2. If none exist, creates one pointing to the Ocean integration route with the needed events (`OAUTH2_WEBHOOK_EVENTS`).


<details>

<summary><b>GitHub Client `_create_events_webhook_oauth` method (Click to expand)</b></summary>

```python showLineNumbers
    async def _create_events_webhook_oauth(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhooks = (
            await self._send_api_request("GET", url=self.webhooks_url)
        ).get("values")

        if webhooks:
            logger.info("Ocean real time reporting webhook already exists")
            return

        # Use a random project in the jqlFilter to ensure we capture everything
        random_project = str(uuid.uuid4())

        body = {
            "url": webhook_target_app_host,
            "webhooks": [
                {
                    "jqlFilter": f"project not in ({random_project})",
                    "events": OAUTH2_WEBHOOK_EVENTS,
                }
            ],
        }

        await self._send_api_request("POST", self.webhooks_url, json=body)
        logger.info("Ocean real time reporting webhook created")

```

</details>

The code uses a JQL filter with a random project to effectively subscribe to **all** projects. If you want a more direct approach, update that filter accordingly.

### Basic Auth-Based Webhooks

If not an OAuth host, `_create_events_webhook` is called. The logic is similar but uses the older `webhooks/1.0/webhook` endpoint and includes a different set of events.


<details>

<summary><b>GitHub Client `_create_events_webhook` method (Click to expand)</b></summary>

```python showLineNumbers
    async def create_webhooks(self, app_host: str) -> None:
        if self.is_oauth_host():
            await self._create_events_webhook_oauth(app_host)
        else:
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

</details>

## Final `JiraClient` Code

Bringing it all together, here’s what your `jira/client.py` file should look like **in full**.


<details>

<summary><b>GitHub Client (Click to expand)</b></summary>

```python
import asyncio
import uuid
from typing import Any, AsyncGenerator, Generator

import httpx
from httpx import Auth, BasicAuth, Request, Response, Timeout
from loguru import logger

from port_ocean.clients.auth.oauth_client import OAuthClient
from port_ocean.context.ocean import ocean
from port_ocean.utils import http_async_client

PAGE_SIZE = 50
WEBHOOK_NAME = "Port-Ocean-Events-Webhook"
MAX_CONCURRENT_REQUESTS = 10

WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
    "project_created",
    "project_updated",
    "project_deleted",
    "project_soft_deleted",
    "project_restored_deleted",
    "project_archived",
    "project_restored_archived",
]

OAUTH2_WEBHOOK_EVENTS = [
    "jira:issue_created",
    "jira:issue_updated",
    "jira:issue_deleted",
]

class BearerAuth(Auth):
    def __init__(self, token: str):
        self.token = token

    def auth_flow(self, request: Request) -> Generator[Request, Response, None]:
        request.headers["Authorization"] = f"Bearer {self.token}"
        yield request

class JiraClient(OAuthClient):
    jira_api_auth: Auth

    def __init__(self, jira_url: str, jira_email: str, jira_token: str) -> None:
        super().__init__()

        self.jira_url = jira_url
        self.jira_rest_url = f"{self.jira_url}/rest"
        self.jira_email = jira_email
        self.jira_token = jira_token

        # Distinguish between OAuth or Basic Auth
        if self.is_oauth_host():
            self.jira_api_auth = self._get_bearer()
            self.webhooks_url = f"{self.jira_rest_url}/api/3/webhook"
        else:
            self.jira_api_auth = BasicAuth(self.jira_email, self.jira_token)
            self.webhooks_url = f"{self.jira_rest_url}/webhooks/1.0/webhook"

        self.api_url = f"{self.jira_rest_url}/api/3"
        self.teams_base_url = f"{self.jira_url}/gateway/api/public/teams/v1/org"

        self.client = http_async_client
        self.client.auth = self.jira_api_auth
        self.client.timeout = Timeout(30)

        self._semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    def is_oauth_host(self) -> bool:
        return "api.atlassian.com" in self.jira_url

    def _get_bearer(self) -> Auth:
        try:
            return BearerAuth(self.external_access_token)
        except ValueError:
            return BearerAuth(self.jira_token)

    def refresh_request_auth_creds(self, request: httpx.Request) -> httpx.Request:
        return next(self._get_bearer().auth_flow(request))

    async def _handle_rate_limit(self, response: Response) -> None:
        if response.status_code == 429:
            logger.warning(
                f"Jira API rate limit reached. Waiting for {response.headers['Retry-After']} seconds."
            )
            await asyncio.sleep(int(response.headers["Retry-After"]))

    async def _send_api_request(
        self,
        method: str,
        url: str,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Any:
        try:
            async with self._semaphore:
                response = await self.client.request(
                    method=method,
                    url=url,
                    params=params,
                    json=json,
                    headers=headers
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPStatusError as e:
            await self._handle_rate_limit(e.response)
            logger.error(
                f"Jira API request failed with status {e.response.status_code}: {method} {url}"
            )
            raise
        except httpx.RequestError as e:
            logger.error(f"Failed to connect to Jira API: {method} {url} - {str(e)}")
            raise

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

    @staticmethod
    def _generate_base_req_params(
        maxResults: int = PAGE_SIZE, startAt: int = 0
    ) -> dict[str, Any]:
        return {
            "maxResults": maxResults,
            "startAt": startAt,
        }

    async def create_webhooks(self, app_host: str) -> None:
        if self.is_oauth_host():
            await self._create_events_webhook_oauth(app_host)
        else:
            await self._create_events_webhook(app_host)

    async def _create_events_webhook_oauth(self, app_host: str) -> None:
        webhook_target_app_host = f"{app_host}/integration/webhook"
        webhooks = (await self._send_api_request("GET", url=self.webhooks_url)).get(
            "values"
        )
        if webhooks:
            logger.info("Ocean real time reporting webhook already exists")
            return

        random_project = str(uuid.uuid4())
        body = {
            "url": webhook_target_app_host,
            "webhooks": [
                {
                    "jqlFilter": f"project not in ({random_project})",
                    "events": OAUTH2_WEBHOOK_EVENTS,
                }
            ],
        }
        await self._send_api_request("POST", self.webhooks_url, json=body)
        logger.info("Ocean real time reporting webhook created")

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

    async def get_single_project(self, project_key: str) -> dict[str, Any]:
        return await self._send_api_request(
            "GET", f"{self.api_url}/project/{project_key}"
        )

    async def get_paginated_projects(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting projects from Jira")
        async for projects in self._get_paginated_data(
            f"{self.api_url}/project/search", "values", initial_params=params
        ):
            yield projects

    async def get_single_issue(self, issue_key: str) -> dict[str, Any]:
        return await self._send_api_request("GET", f"{self.api_url}/issue/{issue_key}")

    async def get_paginated_issues(
        self, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        logger.info("Getting issues from Jira")
        params = params or {}
        if "jql" in params:
            logger.info(f"Using JQL filter: {params['jql']}")

        async for issues in self._get_paginated_data(
            f"{self.api_url}/search", "issues", initial_params=params
        ):
            yield issues

```

</details>

:::tip Formatting your code

Ocean integrations include important development dependencies for formatting your code and sorting imports for consistency across several codebases. These dependencies include `black` and `isort`. You can run them to format your code:

```console
$ poetry run black . && poetry run isort .
```

:::

## Guidelines for Implementing an API Client

- **Ensure the client supports at least one authentication method**: OAuth, Basic Auth, API key, or any other method if authentication is required.
- **Concurrency and Rate-limiting**: Ensure to follow the concurrency and rate-limiting guidelines for the third-party API.
- **Pagination**: Implement dedicated methods to abstract away the pagination logic.
- **Standalone**: The API client should be standalone and not depend on Ocean internals or variables. Exceptions to this rule includes the http client, Ocean's caching utilities and other utility functions. Reading user configurations should be passed from the [resync functions](./sending-data-to-port-using-resync-functions.md) to the client.
- **Logging**: Incorporate logging to help with debugging and troubleshooting.
- **Webhooks**: The client should implement methods to automatically create webhooks for the integration.
- **Single Requests**: Use single, targeted requests for handling webhook events.
- **Data Transformation**: Use the port-app-config mapping to handle any data transformation needed, do not modify the data in the client. This is to ensure users get to choose how they want to transform the data. You can add extra fields to the data returned by the client, however, the keys should be prefixed with a double underscore `__` to avoid conflicts with the data returned by the client. e.g. `__custom_field_name`.

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::
