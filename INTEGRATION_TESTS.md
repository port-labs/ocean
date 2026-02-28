# Ocean Integration Tests

## What this is

An integration test framework that runs a full resync pipeline in-process with zero network calls. You control exactly what the third-party API returns and what Port mapping config is used, then assert on the entities that would be upserted to Port.

The pipeline under test:

```
Third-party API response (you define)
        ↓
@ocean.on_resync handler (real integration code)
        ↓
JQ transformation (real, using your mapping config)
        ↓
Entity upsert to Port (captured by mock, returned to you)
```

## How it works under the hood

### The problem

Ocean has two HTTP client singletons that all integrations use:

1. **`http_async_client`** — for third-party API calls (defined in `port_ocean/utils/async_http.py`)
2. **Port internal client** — for Port API calls (defined in `port_ocean/clients/port/utils.py`)

Both are `httpx.AsyncClient` instances stored in `werkzeug.LocalStack` objects. They're created lazily on first access.

### The solution: transport-layer interception

`httpx.AsyncClient` delegates all actual HTTP work to a **transport** (`httpx.AsyncBaseTransport`). We created `InterceptTransport` — a transport that never hits the network. Instead, it matches incoming requests against a routing table and returns canned responses.

The harness patches both HTTP client singletons with `httpx.AsyncClient` instances backed by `InterceptTransport` *before* the resync runs. All integration code that accesses `http_async_client` or the Port client transparently gets the intercepted version.

Additionally, the harness patches `OceanAsyncClient._init_transport` so that integrations which create their own HTTP clients (rather than using the global `http_async_client`) also get the intercepted transport.

```
Normal flow:
  integration code → http_async_client → RetryTransport → real HTTP → third-party API

Test flow:
  integration code → http_async_client → InterceptTransport → canned response (no network)
```

### What the harness does step by step

1. **Resets the Ocean singleton** — clears `_port_ocean` so a fresh `Ocean` instance can be created
2. **Initializes the signal handler** — required by Ocean's constructor
3. **Creates an `Ocean` app** — using `create_default_app()` with your config overrides and the integration's `spec.yaml`
4. **Loads `main.py`** — this registers `@ocean.on_resync` handlers onto the Ocean app
5. **Patches HTTP clients** — patches both `LocalStack` singletons and `_get_http_client_context` functions, plus `OceanAsyncClient._init_transport`
6. **Initializes handlers** — entity processor (JQ), port app config handler, entities state applier
7. **Calls `sync_raw_all()`** — the real resync method that drives the full pipeline
8. **Collects results** — `PortMockResponder` captures every entity the framework tries to upsert
9. **Cleans up** — stops patches, pops clients off stacks, resets singletons, removes sys.path entries

## Files

```
port_ocean/tests/integration/
├── __init__.py          # Public exports
├── base.py              # BaseIntegrationTest — base class for tests
├── transport.py         # InterceptTransport — the mock httpx transport
├── port_mock.py         # PortMockResponder — pre-wired Port API mock
├── harness.py           # IntegrationTestHarness — boots integration, triggers resync
├── discover.py          # Discovery — captures real API traffic to discovery.json
└── generate.py          # Generator — creates test file from discovery.json
```

### `InterceptTransport`

A mock `httpx.AsyncBaseTransport` with route matching and call logging.

```python
transport = InterceptTransport(strict=False)

# Static response
transport.add_route("GET", "/api/items", {"json": [{"id": 1}]})

# Dynamic response (callable)
transport.add_route("GET", "/api/users", lambda req: {"json": [{"id": "u1"}]})

# Match by regex (auto-detected when url_pattern contains regex chars)
transport.add_route("GET", r"/api/repos/\d+", {"json": {"id": 1}})

# Limit matches (useful for testing pagination or retries)
transport.add_route("GET", "/api/data", {"status_code": 429}, times=1)
transport.add_route("GET", "/api/data", {"json": {"results": []}})

# Inspect what was called
transport.calls                         # all requests
transport.calls_for("/api/items")       # filtered by URL substring
transport.print_call_log()              # formatted summary of all calls
```

**Strict mode** (`strict=True`, default): raises `UnmatchedRequestError` for any request without a matching route. Set `strict=False` to return 404 for unmatched requests instead.

### `PortMockResponder`

Pre-configured `InterceptTransport` that handles the Port API surface needed during resync:

- `POST /v1/auth/access_token` — returns a fake token
- `GET/PATCH /v1/integration/{id}` — returns your mapping config
- `POST /v1/blueprints/{id}/entities/bulk` — captures entities, returns success
- `POST /v1/entities/search` — returns empty results
- `GET/PATCH /v1/blueprints/{id}` — returns blueprint schema
- `DELETE /v1/blueprints/{id}/all-entities` — returns migration ID
- `GET /v1/migrations/{id}` — returns COMPLETE
- `GET /v1/organization` — returns empty feature flags

After a resync, all entities that the framework tried to upsert are in `port_mock.upserted_entities`.

### `IntegrationTestHarness`

The test driver. Boots the integration, patches transports, triggers resync:

```python
harness = IntegrationTestHarness(
    integration_path="./",                      # path to the integration directory
    port_mapping_config=mapping_config,          # Port mapping config dict
    third_party_transport=my_transport,           # your InterceptTransport for the third-party
    config_overrides={"integration": {...}},      # optional config overrides
)
await harness.start()
result = await harness.trigger_resync()
# result.upserted_entities — entities that would be sent to Port
# result.errors — any exceptions during resync
await harness.shutdown()
```

### `BaseIntegrationTest`

Base class that reduces per-integration test boilerplate. Handles harness lifecycle automatically:

```python
class TestMyIntegration(BaseIntegrationTest):
    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        transport = InterceptTransport(strict=False)
        transport.add_route("GET", "/api/items", {"json": [{"id": 1}]})
        return transport

    def create_mapping_config(self) -> dict:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "enableMergeEntity": True,
            "resources": [...]
        }

    def create_integration_config(self) -> dict:
        return {"integration": {"identifier": "test", "type": "my-type", "config": {}}}

    @pytest.mark.asyncio
    async def test_resync_produces_entities(self, resync: ResyncResult):
        assert len(resync.upserted_entities) > 0
```

Two fixtures are provided automatically:
- **`harness`** — a started `IntegrationTestHarness` (auto-shutdown after test)
- **`resync`** — a `ResyncResult` from triggering a resync (use when you just need results)

Use `harness` directly when you need to interact with the harness (e.g., inspect call logs). Use `resync` when you only need the upserted entities.

## Quick start — auto-generate a test

The fastest path to a working integration test:

```bash
cd integrations/my-integration

# 1. Set up real credentials in .env (for discovery)
echo 'OCEAN__INTEGRATION__CONFIG__MY_TOKEN=real-token-here' > .env

# 2. Run discovery — captures all HTTP requests/responses to discovery.json
make test/integration/discover

# 3. Generate a test file from the captured data
make test/integration/generate

# 4. Run the generated test
make test/integration
```

This produces a `tests/test_integration_resync.py` with mocked routes, mapping config, and a smoke test — ready to run and customize. See [Discovery](#discovery) and [Test generation](#test-generation) below for details.

## Makefile targets

Run these from an integration directory (`integrations/my-integration/`):

| Target | Description |
|--------|-------------|
| `make test/integration` | Run `tests/test_integration_resync.py` |
| `make test/integration/discover` | Run a real resync, capture all HTTP traffic to `.port/resources/discovery.json` |
| `make test/integration/generate` | Generate `tests/test_integration_resync.py` from `discovery.json` |

## Running integration tests

From any integration directory:

```bash
cd integrations/{name}
make install/local-core    # one-time: install local Ocean core with the test framework
poetry run pytest tests/test_integration_resync.py -xvs -o "addopts="
```

### Why `-xvs -o "addopts="`?

- **`-x`** — stop on first failure (useful during development)
- **`-v`** — verbose output showing test names
- **`-s`** — don't capture stdout (lets you see log output)
- **`-o "addopts="`** — overrides the default `addopts = -n auto` in `pyproject.toml`, which runs tests in parallel via pytest-xdist. Integration tests must run serially because they modify global state (Ocean singleton, HTTP client stacks).

Without `-o "addopts="`, pytest-xdist spins up worker processes that interfere with each other. You'll see cryptic failures if you forget this flag.

### Quick reference

```bash
# Run all integration tests
poetry run pytest tests/test_integration_resync.py -xvs -o "addopts="

# Run a specific test class
poetry run pytest tests/test_integration_resync.py::TestMyIntegration -xvs -o "addopts="

# Run a specific test method
poetry run pytest tests/test_integration_resync.py::TestMyIntegration::test_resync -xvs -o "addopts="
```

## Writing integration tests for a new integration

### Step 1: Discover what URLs your integration calls

You have three options, from easiest to most manual:

**Option A: Auto-generate (recommended)**

Use the discovery + generation pipeline to get a working test automatically. See [Quick start](#quick-start--auto-generate-a-test) above. Then skip to Step 3.

**Option B: Discovery mode with `.env`**

If you have real API credentials, run discovery to capture all HTTP traffic:

```bash
# Set up credentials
echo 'OCEAN__INTEGRATION__CONFIG__API_TOKEN=real-token' > .env

# Run discovery
make test/integration/discover
```

This creates `.port/resources/discovery.json` with all requests/responses. You can then either run `make test/integration/generate` to auto-generate the test, or use the JSON as a reference while writing the test manually.

**Option C: Manual discovery**

Read the integration's `main.py` and client code. Search for `http_async_client.get(`, `self.client.get(`, etc. Identify:
- What URLs does it call on the third-party API?
- What does the response format look like?
- What resource kinds does it define in `@ocean.on_resync`?

You can also run a resync with `strict=False` and inspect the call log programmatically:

```python
harness = IntegrationTestHarness(
    integration_path=INTEGRATION_PATH,
    port_mapping_config=minimal_mapping_config,
    third_party_transport=InterceptTransport(strict=False),  # returns 404 for everything
    config_overrides=integration_config,
)
await harness.start()
output = await harness.discover_requests()
# Prints all unique URLs the integration called, marking unmatched ones
await harness.shutdown()
```

You can also use `print_call_log()` on any transport after a resync to see the full HTTP call history:

```python
result = await harness.trigger_resync()
harness.third_party_transport.print_call_log()           # third-party calls only
harness.port_mock.transport.print_call_log()             # Port API calls
harness.third_party_transport.print_call_log(include_port=True)  # include Port calls too
```

### Step 2: Create the test file

Create `integrations/{name}/tests/test_integration_resync.py`.

**Using the base class (recommended):**

```python
import os
from typing import Any
import pytest
from port_ocean.tests.integration import BaseIntegrationTest, InterceptTransport, ResyncResult

class TestMyIntegration(BaseIntegrationTest):
    integration_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))

    def create_third_party_transport(self) -> InterceptTransport:
        transport = InterceptTransport(strict=False)
        transport.add_route(
            "GET",
            "api.example.com/v2/projects",
            {"json": [{"id": "proj-1", "name": "My Project", "status": "active"}]},
        )
        return transport

    def create_mapping_config(self) -> dict[str, Any]:
        return {
            "deleteDependentEntities": True,
            "createMissingRelatedEntities": True,
            "enableMergeEntity": True,
            "resources": [
                {
                    "kind": "project",
                    "selector": {"query": "true"},
                    "port": {
                        "entity": {
                            "mappings": {
                                "identifier": ".id",
                                "title": ".name",
                                "blueprint": '"myBlueprint"',
                                "properties": {
                                    "projectName": ".name",
                                    "projectStatus": ".status",
                                },
                                "relations": {},
                            }
                        }
                    },
                },
            ],
        }

    def create_integration_config(self) -> dict[str, Any]:
        return {
            "integration": {
                "identifier": "test-my-integration",
                "type": "my-integration",
                "config": {
                    "api_token": "fake-token",
                    "api_url": "https://api.example.com",
                },
            },
        }

    @pytest.mark.asyncio
    async def test_resync_creates_expected_entities(self, resync: ResyncResult) -> None:
        assert len(resync.upserted_entities) == 1
        entity = resync.upserted_entities[0]
        assert entity["identifier"] == "proj-1"
        assert entity["blueprint"] == "myBlueprint"
        assert entity["properties"]["projectName"] == "My Project"
```

**Key detail**: The `"kind"` in the mapping config must match the kind string in `@ocean.on_resync("kind")` — this is how the framework knows which handler to call for which resource.

**Using separate test classes for different scenarios**: Create multiple classes inheriting from `BaseIntegrationTest`, each with different transport/mapping configurations:

```python
class TestMyIntegrationBasic(BaseIntegrationTest):
    # ... basic happy-path config

class TestMyIntegrationWithFilter(BaseIntegrationTest):
    # ... config with JQ selector filter

class TestMyIntegrationErrorHandling(BaseIntegrationTest):
    # ... config with error responses from third-party
```

### Step 3: Run it

```bash
cd integrations/{name}
make install/local-core
poetry run pytest tests/test_integration_resync.py -xvs -o "addopts="
```

## Test patterns

### Testing JQ selector filtering

Use different `selector.query` values to test filtering:

```python
# Only active projects
"selector": {"query": '.status == "active"'}

# Projects with more than 10 members
"selector": {"query": '.member_count > 10'}
```

### Testing third-party errors

Return error status codes to verify the integration handles them:

```python
transport.add_route("GET", "/api/data", {"status_code": 500, "json": {"error": "fail"}})
```

### Testing pagination / retries

Use `times` to return different responses on subsequent calls:

```python
# First call returns 429, second call succeeds
transport.add_route("GET", "/api/data", {"status_code": 429}, times=1)
transport.add_route("GET", "/api/data", {"json": {"results": [...]}})
```

### Testing dynamic responses

Use a callable to vary the response based on the request:

```python
def handle_request(request):
    dept_id = str(request.url).split("/")[-1]
    return {"json": [{"id": f"person-in-{dept_id}"}]}

transport.add_route("GET", "/api/departments/", handle_request)
```

### Inspecting HTTP call history

After a resync, check what HTTP calls were made:

```python
result = await harness.trigger_resync()

# All third-party calls
all_calls = third_party_transport.calls

# Calls to a specific endpoint
project_calls = third_party_transport.calls_for("/api/projects")
assert len(project_calls) == 1
assert project_calls[0].response.status_code == 200

# Print formatted call log
third_party_transport.print_call_log()
```

## Integrations with custom HTTP clients

Some integrations create their own `OceanAsyncClient` instead of using the global `http_async_client`. The harness automatically handles this by patching `OceanAsyncClient._init_transport` to inject the test transport. No extra configuration is needed — any `OceanAsyncClient` created during the test will use the intercepted transport.

## Discovery

Discovery (`port_ocean.tests.integration.discover`) runs your integration against real APIs and records every HTTP request/response into `.port/resources/discovery.json`.

### Prerequisites

Create a `.env` file in your integration directory with real credentials:

```bash
# integrations/github/.env
OCEAN__INTEGRATION__CONFIG__GITHUB_HOST=https://api.github.com
OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN=ghp_xxxxxxxxxxxx
OCEAN__INTEGRATION__CONFIG__GITHUB_ORGANIZATION=my-org
```

Environment variable names follow the pattern `OCEAN__INTEGRATION__CONFIG__<SCREAMING_SNAKE_CASE>` where the config name from `spec.yaml` is converted from camelCase (e.g., `githubHost` → `GITHUB_HOST`).

### Running

```bash
cd integrations/my-integration
make test/integration/discover
```

### Output format

The resulting `.port/resources/discovery.json` contains:

| Field | Description |
|-------|-------------|
| `metadata` | Integration type and generation timestamp |
| `integration_config` | The config used (from `.env` + `spec.yaml` defaults) |
| `mapping_config` | From `.port/resources/port-app-config.yml` |
| `blueprints` | From `.port/resources/blueprints.json` |
| `third_party_requests` | All third-party HTTP requests with full request/response data |
| `port_requests` | All Port API requests made during resync |

Each request entry in `third_party_requests` looks like:

```json
{
  "method": "GET",
  "url": "https://api.github.com/orgs/my-org/repos",
  "request_headers": { ... },
  "request_body": null,
  "response_status": 200,
  "response_body": [ ... ]
}
```

### Without credentials

If no `.env` is provided, discovery runs with dummy config values (from `spec.yaml` defaults) and a mock transport that returns 404 for everything. This is useful for seeing what URLs the integration tries to call, even if the responses are all failures.

## Test generation

The generator (`port_ocean.tests.integration.generate`) reads `discovery.json` and produces a ready-to-run test file.

### Running

```bash
cd integrations/my-integration
make test/integration/generate
```

This writes `tests/test_integration_resync.py`.

### What it does

1. **Reads** `.port/resources/discovery.json`
2. **Groups** third-party requests into URL patterns using a recursive splitting algorithm
3. **Picks** the best representative response for each pattern (prefers 2xx)
4. **Truncates** array responses to 2 items to keep the file small
5. **Sanitizes** sensitive config values (tokens, secrets, keys, passwords) → `"test-value"`
6. **Writes** a complete test file with `BaseIntegrationTest` subclass and a smoke test

### URL pattern detection algorithm

Given requests like:
```
GET /repos/my-org/repo-1/contents/README.md → 200
GET /repos/my-org/repo-2/contents/README.md → 200
GET /repos/my-org/repo-1/contents/CODEOWNERS → 404
GET /orgs/my-org/repos → 200
GET /orgs/my-org/installation → 200
```

The algorithm:
1. Groups requests by `(method, base_url, segment_count)`
2. Recursively splits groups: if a segment position has few (≤3) distinct values, it splits into subgroups to avoid merging structurally different endpoints (e.g., `/orgs/...` stays separate from `/repos/...`)
3. Positions with many distinct values become `[^/]+` wildcards
4. Routes are ordered with specific patterns before catch-all patterns

Result:
```python
transport.add_route("GET", "/orgs/my-org/installation", {"json": {...}})
transport.add_route("GET", "/orgs/my-org/repos", {"json": [...]})
transport.add_route("GET", r"/repos/my-org/[^/]+/contents/CODEOWNERS", {"status_code": 404})
transport.add_route("GET", r"/repos/my-org/[^/]+/contents/README.md", {"json": {...}})
```

### Sensitive data handling

Config values whose keys match patterns like `token`, `secret`, `key`, `password`, `credential`, `auth`, or `private` are replaced with `"test-value"` in the generated test. Response bodies are kept as-is (they contain API data, not credentials).

### Customizing the generated test

The generated file is a starting point. Common customizations:

- **Add specific assertions** — check entity counts, blueprint types, property values
- **Adjust mock responses** — modify response bodies to test edge cases
- **Add error scenarios** — test how the integration handles 401s, 500s, rate limits
- **Add multiple test methods** — test different resource kinds separately

```python
@pytest.mark.asyncio
async def test_resync_creates_repos(self, resync: ResyncResult) -> None:
    repos = [
        e for e in resync.upserted_entities
        if e.get("blueprint") == "githubRepository"
    ]
    assert len(repos) == 2
    assert all(r.get("identifier") for r in repos)
```
