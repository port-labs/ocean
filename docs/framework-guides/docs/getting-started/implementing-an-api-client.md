---
sidebar_position: 2
---

# 🔗 Implementing an API Client
One of the first steps to implementing an integration with Ocean is to create an API client. This client will be responsible for interacting with the third-party API and pulling in the data that you need to send to Port. In this case, our client, `GitHubClient`, will be interacting with the GitHub API.

We are interested in three APIs respectively:
- [GitHub Organization Detail API](https://docs.github.com/en/rest/orgs/orgs?apiVersion=2022-11-28#get-an-organization): This API will be used to get the details of a GitHub organization.
- [GitHub Repositories API](https://docs.github.com/en/rest/repos/repos?apiVersion=2022-11-28#list-organization-repositories): This API will be used to get the repositories of a GitHub organization.
- [GitHub Pull Requests API](https://docs.github.com/en/rest/pulls/pulls?apiVersion=2022-11-28#list-pull-requests): This API will be used to get the pull requests of a GitHub repository.


## GitHubClient
We create a `client.py` file in the `github` directory. This file will contain the `GitHubClient` class, which will be responsible for interacting with the GitHub API.

```console
$ touch client.py
```

### The GitHubClient Constructor
We will define the client to accept a few parameters in its constructor:
- `base_url`: The base URL of the GitHub API. It is possible that the GitHub instance is self-hosted, so we need to be able to configure the base URL.
- `access_token`: The access token to authenticate with the GitHub API. This is required for making requests to the GitHub API. Since tokens are only required when dealing with private repositories, we will make this parameter optional.

In addition, we will add an attribute for the http client we will be using to make requests. Since Ocean integrations with speed and performance in mind, we will be using Python's async features which naturally leads us to use a robust async http client, [httpx](https://www.python-httpx.org/). Fortunately, the `httpx` library is already included in the Ocean framework with helper features such as exponential backoff retry mechanism and other sensible defaults so we don't need to install or configure it separately.


<details>

<summary><b>GitHub Client constructor (Click to expand)</b></summary>

```python showLineNumbers
from port_ocean.utils import http_async_client

class GitHubClient:
    def __init__(self, base_url: str ="https://api.github.com", access_token: str | None = None) -> None:
        self.base_url = base_url
        self.access_token = access_token
        self.http_client = http_async_client

    # Other methods will be added here

```

</details>

One thing remains: we haven't yet added the headers required for authentication. We will do that with a `headers` property since the `access_token` is optional. If the `access_token` is provided, we will add the `Authorization` header to the request.


<details>

<summary><b>GitHub Client headers property (Click to expand)</b></summary>

```python showLineNumbers
from port_ocean.utils import http_async_client


class GitHubClient:
    def __init__(self, base_url: str ="https://api.github.com", access_token: str | None = None) -> None:
        self.base_url = base_url
        self.access_token = access_token
        self.http_client = http_async_client
// highlight-start
        self.http_client.headers.update(self.headers)

    @property
    def headers(self) -> dict[str, str]:
        initial_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28"
        }
        if self.access_token:
            initial_headers["Authorization"] = f"Bearer {self.access_token}"

        return initial_headers
// highlight-end

    # Other methods will be added here

```

</details>

#### Rate Limiting
When building an integration, it is important to be mindful of the rate limits of the API you are interacting with. GitHub has a rate limit of 5000 requests per hour for authenticated requests, and 60 requests per hours for unauthenticated requests. We could implement a `LeakyBucketRateLimiter` class to handle this, but there is a library specifically built to work with async code (or `asyncio` as it is called) called [`aiolimiter`](https://aiolimiter.readthedocs.io/).

Let's install it with Poetry:

```console
$ poetry add aiolimiter
```

We will create a `rate_limiter` property that will contain an instance of the `aiolimiter.AsyncLimiter` class. The arguments passed to the `AsyncLimiter` depends on the authentication status of the client.


<details>

<summary><b>GitHub Client `rate_limiter` property (Click to expand)</b></summary>

```python showLineNumbers
// highlight-next-line
from aiolimiter import AsyncLimiter
from port_ocean.utils import http_async_client


class GitHubClient:
    // highlight-start
    REQUEST_LIMIT_AUTHENTICATED = 5000
    REQUEST_LIMIT_UNAUTHENTICATED = 60
    // highlight-end

    def __init__(
        self, base_url: str ="https://api.github.com", access_token: str | None = None
    ) -> None:
        self.base_url = base_url
        self.access_token = access_token
        self.http_client = http_async_client
        self.http_client.headers.update(self.headers)
        // highlight-start
        time_period = 60 * 60  # 1 hour in seconds
        self.rate_limiter = AsyncLimiter((
            self.REQUEST_LIMIT_AUTHENTICATED
            if self.access_token
            else self.REQUEST_LIMIT_UNAUTHENTICATED
        ), time_period)
        // highlight-end

    @property
    def headers(self) -> dict[str, str]:
        initial_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.access_token:
            initial_headers["Authorization"] = f"Bearer {self.access_token}"

        return initial_headers

    # Other methods will be added here

```

</details>


### Implementing the method to retrieve organization details
Since we are going to work with specific organizations input by the user, we will create a method to retrieve information on a specific organization so we can have data to export to Port. We could start by creating a method to retrieve the organization details:

<details>

<summary><b>GitHub Client get_organization method (Click to expand)</b></summary>

```python showLineNumbers
// highlight-next-line
import httpx
from aiolimiter import AsyncLimiter
// highlight-next-line
from loguru import logger
from port_ocean.utils import http_async_client


class GitHubClient:
    # rest of the class

    async def get_organization(self, organization: str) -> dict:
        url = f"{self.base_url}/orgs/{organization}"
        async with self.rate_limiter:
            try:
                response = await self.http_client.get(
                    url
                )
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Got HTTP error when making reques to {url} with "
                    f"status code: {e.response.status_code} and response:"
                    f" {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Got HTTP error when making request to {url} with "
                    f"error: {e}"
                )
                raise
```

</details>

But there are a few problems here:
- We would have to loop through each of the organizations to get the details of each organization. This is not efficient since each iteration is synchronous and will block the event loop, therefore, having an async function makes little to no difference. To fix this, the caller would have to use `asyncio.gather` which would make the calling code complex.

- Other methods added to the `GitHubClient` class will have to duplicate the same wrapper code including the rate limit context manager and the try-except block. This is not DRY (Don't Repeat Yourself) and is not maintainable.


To remedy this, first, we will define a separate method to make API requests, handle rate limiting, and error handling. This method will be used by all other methods in the `GitHubClient` class. We will call this method `_send_api_request`. Secondly, the `get_organization` method will be renamed to `get_organizations` and refactored to accept a list of organizations and return a list of organization details.

<details>

<summary><b>Refactoring the `get_organization` method (Click to expand)</b></summary>

```python showLineNumbers
import asyncio
from typing import Any
# remaining imports


// highlight-start
class Endpoints:
    ORGANIZATION = "orgs/{}"
// highlight-end


class GitHubClient:
    # rest of the class

// highlight-start
    async def _send_api_request(self, url: str) -> dict[str, Any]:
        async with self.rate_limiter:
            try:
                response = await self.http_client.get(
                    url
                )
                return response.json()
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Got HTTP error when making reques to {url} with "
                    f"status code: {e.response.status_code} and response:"
                    f" {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Got HTTP error when making request to {url} with "
                    f"error: {e}"
                )
                raise

    async def get_organizations(self, organizations: list[str]) -> list[dict[str, Any]]:
        tasks = [
            self._send_api_request(
                f"{self.base_url}/{Endpoints.ORGANIZATION.format(org)}"
            )
            for org in organizations
        ]

        return await asyncio.gather(*tasks)

// highlight-end

```

</details>

:::tip Modifying the returned data
Despite the fact that we can modify the data returned by GitHub to fit a specific usecase, it is better to return the data as-is and rely on using the integration mapping to handle data transforms. This way, the integration is more flexible and can be reused for other usecases. If there is the pressing need to modify the data, opt to add a custom property to the returned data prefixed by a double underscore, `__`, to indicate that the data is not the original data returned by the API.
:::



### Retrieving repositories of an organization
The endpoint for retrieving repositories of an organization is a paginaged endpoint.
Since the we expect to use another endpoint which also requires pagination, it would be smart
to implement a method that can handle pagination. We will create a method called `_get_paginated_data` that will be used by the `get_repositories` and `get_pull_requests` methods.
This method will make use of the already existing `_send_api_request` method to make requests to the GitHub API.

However, GitHub's pagination is done using the `Link` header in the response. The `Link` header contains the URL to the next page of results. We will need to extract this URL and make a request to it to get the next page of results.
Since the `_send_api_request` method returns only the data, we will modify it to return the response object itself and calling methods will extract the JSON data they need.
 We will also create a helper method called `_get_next_page_url` to extract the URL from the `Link` header.

<details>

<summary><b>Retrieving repositories of an organization (Click to expand)</b></summary>

```python showLineNumbers
# remaining imports
// highlight-start
from typing import Any, AsyncGenerator

type RepositoryType = Literal["all", "public", "private", "forks", "sources", "member"]
// highlight-end

class Endpoints:
    ORGANIZATION = "orgs/{}"
// highlight-next-line
    REPOSITORY = "orgs/{}/repos"



class GitHub:
    # rest of the class

// highlight-start
    def _get_next_page_url(self, response: httpx.Headers) -> str | None:
        link: str = response.get("Link", None)
        if not link:
            return None

        links = link.split(",")
        for link in links:
            url, rel = link.split(";")
            if "next" in rel:
                return url.strip("<> ")

        return None
// highlight-end


// highlight-next-line
    async def _send_api_request(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        async with self.rate_limiter:
// highlight-next-line
            logger.info(f"Making request to {url} with params: {params}")
            try:
                response = await self.http_client.get(
                    url,
// highlight-next-line
                    params=params
                )
// highlight-next-line
                return response
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Got HTTP error when making reques to {url} with "
                    f"status code: {e.response.status_code} and response:"
                    f" {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Got HTTP error when making request to {url} with "
                    f"error: {e}"
                )
                raise

// highlight-start
    async def _get_paginated_data(self, url: str, params: dict[str, Any] | None = None) -> AsyncGenerator[list[dict[str, Any]], None]:
        next_url: str | None = url

        while next_url:
            data = await self._send_api_request(next_url, params)
            response = data.json()
            yield response

            next_url = self._get_next_page_url(data.headers)
// highlight-end

    async def get_organizations(self, organizations: list[str]) -> list[dict[str, Any]]:
        tasks = [
            self._send_api_request(
                f"{self.base_url}/{Endpoints.ORGANIZATION.format(org)}"
            )
            for org in organizations
        ]

// highlight-next-line
        return [res.json() for res in await asyncio.gather(*tasks)]

// highlight-start
    async def get_repositories(self, organizations: list[str], repo_type: RepositoryType) -> AsyncGenerator[list[dict[str, Any]], None]:
        for org in organizations:
            async for data in self._get_paginated_data(
                f"{self.base_url}/{Endpoints.REPOSITORY.format(org)}",
                {"type": repo_type}
            ):
                yield data
// highlight-end

```

</details>


We made a few changes to the `GitHubClient` class:

- Since the headers are needed from the response object, we modified the `_send_api_request` method to return the response object instead of the JSON data.
- We also add a `params` argument to the `_send_api_request` method to allow for passing query parameters to the request.
- We modify the `get_organizations` method to return the JSON data from the response object.


The `get_repositories` method is an asynchoronous generator that yields the repositories as soon as they are retrieved.
This is useful when working with large datasets as it allows the caller to process the data as it is being retrieved.
The caller can use the `async for` syntax to iterate over the data. However, we face a small problem as we did with the `get_organizations` method:
despite using async code, each of the organizations will be retrieved sequentially. This is not efficient as we are not taking full advantage of the async features of Python.
Also, using `async.gather` would be rather messy and complex. Thankfully, Ocean provides a helper utility function just for this purpose: `port_ocean.utils.async_iterators.stream_async_iterators_tasks`.


<details>

<summary><b>Using the `stream_async_iterators_tasks` function (Click to expand)</b></summary>

```python showLineNumbers
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
# remaining imports

# ... rest of code


class GitHub:
    # rest of the class

// highlight-start
    async def get_repositories(self, organizations: list[str], repo_type: RepositoryType) -> AsyncGenerator[list[dict[str, Any]], None]:
        tasks = [
            self._get_paginated_data(
                f"{self.base_url}/{Endpoints.REPOSITORY.format(org)}",
                {"type": repo_type}
            )
            for org in organizations
        ]

        async for repositories in stream_async_iterators_tasks(*tasks):
            yield repositories

// highlight-end
```

</details>

The `stream_async_iterators_tasks` function takes in a list of async iterators and returns an async generator that yields the results of each async iterator as they are retrieved. This is a much cleaner and more efficient way to retrieve data from multiple async iterators.


### Retrieving pull requests of a repository
The endpoint for retrieving pull requests of a repository is also paginated. We will create a method called `get_pull_requests` that will be similar to the `get_repositories` method. The `get_pull_requests` method will also use the `_get_paginated_data` method to handle pagination.


<details>

<summary><b>Retrieving pull requests of a repository (Click to expand)</b></summary>

```python showLineNumbers
# rest of code

// highlight-next-line
type PullRequestState = Literal["open", "closed", "all"]


class Endpoints:
    ORGANIZATION = "orgs/{}"
    REPOSITORY = "orgs/{}/repos"
// highlight-next-line
    PULL_REQUESTS = "repos/{}/pulls"

class GitHub:
    # rest of the class
    async def get_pull_requests(self, organizations: list[str], repo_type: RepositoryType, state: PullRequestState) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repositories in self.get_repositories(organizations, repo_type):
            tasks = [
                self._get_paginated_data(
                    f"{self.base_url}/{Endpoints.PULL_REQUESTS.format(repository['full_name'])}",
                    {"state": state}
                )
                for repository in repositories
            ]

            async for pull_requests in stream_async_iterators_tasks(*tasks):
                yield pull_requests


```

</details>

### Caching the results of API calls
We have successfully implemented the `GitHubClient` class with methods to retrieve organization details, repositories of an organization, and pull requests of a repository.
We have also handled pagination and rate limiting. The `GitHubClient` class is now ready to be used to interact with the GitHub API.
Just one thing is left: the `get_pull_requests` method calls the `get_repositories` method to retrieve repositories
before retrieving the pull requests. This is not efficient as we are making two separate requests to the GitHub API.
We can make things better by caching the repositories and reusing them when retrieving the pull requests. Ocean provides a
helper function `port_ocean.utils.cache.cache_iterator_result` that can be used to cache the results of an async iterator.
All we have to do is decorate the `get_repositories` method with the `cache_iterator_result` decorator and the results will be cached.


<details>

<summary><b>Caching the results of the `get_repositories` method (Click to expand)</b></summary>

```python showLineNumbers
# rest of imports
from port_ocean.utils.cache import cache_iterator_result

# rest of code

class GitHub:
    # rest of the class

// highlight-next-line
    @cache_iterator_result()
    async def get_repositories(self, organizations: list[str], repo_type: RepositoryType) -> AsyncGenerator[list[dict[str, Any]], None]:
        tasks = [
            self._get_paginated_data(
                f"{self.base_url}/{Endpoints.REPOSITORY.format(org)}",
                {"type": repo_type}
            )
            for org in organizations
        ]

        async for repositories in stream_async_iterators_tasks(*tasks):
            yield repositories


```

</details>


## Conclusion

We have successfully implemented the `GitHubClient` class with methods to retrieve organization details, repositories of an organization, and pull requests of a repository.

Your `client.py` file should look like this:

<details>

<summary><b>GitHub Client (Click to expand)</b></summary>

```python showLineNumbers
import asyncio
from typing import Any, AsyncGenerator, Literal

import httpx
from aiolimiter import AsyncLimiter
from loguru import logger
from port_ocean.utils import http_async_client
from port_ocean.utils.async_iterators import stream_async_iterators_tasks
from port_ocean.utils.cache import cache_iterator_result

type RepositoryType = Literal["all", "public", "private", "forks", "sources", "member"]
type PullRequestState = Literal["open", "closed", "all"]


class Endpoints:
    ORGANIZATION = "orgs/{}"
    REPOSITORY = "orgs/{}/repos"
    PULL_REQUESTS = "repos/{}/pulls"


class GitHubClient:
    REQUEST_LIMIT_AUTHENTICATED = 5000
    REQUEST_LIMIT_UNAUTHENTICATED = 60

    def __init__(
        self, base_url: str = "https://api.github.com", access_token: str | None = None
    ) -> None:
        self.base_url = base_url
        self.access_token = access_token
        self.http_client = http_async_client
        self.http_client.headers.update(self.headers)
        time_period = 60 * 60  # 1 hour in seconds
        self.rate_limiter = AsyncLimiter((
            self.REQUEST_LIMIT_AUTHENTICATED
            if self.access_token
            else self.REQUEST_LIMIT_UNAUTHENTICATED
        ), time_period)

    @property
    def headers(self) -> dict[str, str]:
        initial_headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }
        if self.access_token:
            initial_headers["Authorization"] = f"Bearer {self.access_token}"

        return initial_headers

    def _get_next_page_url(self, response: httpx.Headers) -> str | None:
        link: str = response.get("Link", None)
        if not link:
            return None

        links = link.split(",")
        for link in links:
            url, rel = link.split(";")
            if "next" in rel:
                return url.strip("<> ")

        return None

    async def _send_api_request(
        self, url: str, params: dict[str, Any] | None = None
    ) -> httpx.Response:
        async with self.rate_limiter:
            logger.info(f"Making request to {url} with params: {params}")
            try:
                response = await self.http_client.get(url, params=params)
                return response
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"Got HTTP error when making reques to {url} with "
                    f"status code: {e.response.status_code} and response:"
                    f" {e.response.text}"
                )
                raise
            except httpx.HTTPError as e:
                logger.error(
                    f"Got HTTP error when making request to {url} with " f"error: {e}"
                )
                raise

    async def _get_paginated_data(
        self, url: str, params: dict[str, Any] | None = None
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        next_url: str | None = url

        while next_url:
            data = await self._send_api_request(next_url, params)
            response = data.json()
            yield response

            next_url = self._get_next_page_url(data.headers)

    async def get_organizations(self, organizations: list[str]) -> list[dict[str, Any]]:
        tasks = [
            self._send_api_request(
                f"{self.base_url}/{Endpoints.ORGANIZATION.format(org)}"
            )
            for org in organizations
        ]

        return [res.json() for res in await asyncio.gather(*tasks)]

    @cache_iterator_result()
    async def get_repositories(
        self, organizations: list[str], repo_type: RepositoryType
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        tasks = [
            self._get_paginated_data(
                f"{self.base_url}/{Endpoints.REPOSITORY.format(org)}",
                {"type": repo_type},
            )
            for org in organizations
        ]

        async for repositories in stream_async_iterators_tasks(*tasks):
            yield repositories

    async def get_pull_requests(
        self,
        organizations: list[str],
        repo_type: RepositoryType,
        state: PullRequestState,
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        async for repositories in self.get_repositories(organizations, repo_type):
            tasks = [
                self._get_paginated_data(
                    f"{self.base_url}/{Endpoints.PULL_REQUESTS.format(repository['full_name'])}",
                    {"state": state},
                )
                for repository in repositories
            ]

            async for pull_requests in stream_async_iterators_tasks(*tasks):
                yield pull_requests

```

</details>


:::tip Formatting your code
Remember to format your code using [`black`](https://black.readthedocs.io/en/stable/) and sort imports with [`isort`](https://pycqa.github.io/isort/) before proceeding. You can do this by running the following command:

```console
$ poetry run black . && poetry run isort .
```

:::tip Source Code
You can find the source code for the integration in the [Developing An Integration repository on GitHub](https://github.com/port-labs/developing-an-integration)

:::

Next, we will look at integration configurations, kinds and sending data to Port.
