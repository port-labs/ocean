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

The harness pushes `httpx.AsyncClient` instances (backed by `InterceptTransport`) onto the `LocalStack` singletons *before* the resync runs. Since `LocalStack.top` returns the most recently pushed value, all integration code that accesses `http_async_client` or the Port client transparently gets the intercepted version.

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
5. **Patches HTTP clients** — pushes intercepted clients onto both `LocalStack` singletons
6. **Initializes handlers** — entity processor (JQ), port app config handler, entities state applier
7. **Calls `sync_raw_all()`** — the real resync method that drives the full pipeline
8. **Collects results** — `PortMockResponder` captures every entity the framework tries to upsert
9. **Cleans up** — pops clients off stacks, resets singletons, removes sys.path entries

## Files

```
port_ocean/tests/integration/
├── __init__.py          # Public exports
├── transport.py         # InterceptTransport — the mock httpx transport
├── port_mock.py         # PortMockResponder — pre-wired Port API mock
└── harness.py           # IntegrationTestHarness — boots integration, triggers resync
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

## Running integration tests

From any integration directory:

```bash
cd integrations/{name}
make install/local-core    # one-time: install local Ocean core with the test framework
poetry run pytest tests/test_integration_resync.py -xvs -o "addopts="
```

The `-o "addopts="` overrides the default `-n auto` (parallel execution) so you get serial execution with visible output.

## Writing integration tests for a new integration

### Step 1: Understand the integration's HTTP calls

Read the integration's `main.py` and client code. Identify:
- What URLs does it call on the third-party API?
- What does the response format look like?
- What resource kinds does it define in `@ocean.on_resync`?

### Step 2: Create the test file

Create `integrations/{name}/tests/test_integration_resync.py`:

```python
import os
import pytest
from port_ocean.tests.integration import InterceptTransport, IntegrationTestHarness

INTEGRATION_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../"))
```

### Step 3: Define third-party fixtures

Create an `InterceptTransport` with routes matching the URLs your integration calls:

```python
@pytest.fixture
def third_party_transport() -> InterceptTransport:
    transport = InterceptTransport(strict=False)

    # Match the URLs your integration actually calls
    transport.add_route(
        "GET",
        "api.example.com/v2/projects",
        {
            "json": [
                {"id": "proj-1", "name": "My Project", "status": "active"},
            ]
        },
    )

    return transport
```

**How to find the right URLs**: Look at the integration's client code. Search for `http_async_client.get(`, `self.client.get(`, etc. The URL patterns in your routes need to match what the integration actually calls.

### Step 4: Define mapping config

This is the Port mapping configuration — it defines how raw third-party data maps to Port entities via JQ expressions:

```python
@pytest.fixture
def mapping_config() -> dict:
    return {
        "deleteDependentEntities": True,
        "createMissingRelatedEntities": True,
        "enableMergeEntity": True,
        "resources": [
            {
                "kind": "project",                              # matches @ocean.on_resync("project")
                "selector": {"query": "true"},                  # JQ filter (true = accept all)
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".id",                # JQ: raw_data.id → entity identifier
                            "title": ".name",                   # JQ: raw_data.name → entity title
                            "blueprint": '"myBlueprint"',       # literal string (note the quotes)
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
```

**Key detail**: The `"kind"` in the mapping config must match the kind string in `@ocean.on_resync("kind")` — this is how the framework knows which handler to call for which resource.

### Step 5: Define integration config

Override any integration-specific settings your integration reads from `ocean.integration_config`:

```python
@pytest.fixture
def integration_config() -> dict:
    return {
        "integration": {
            "identifier": "test-my-integration",
            "type": "my-integration",
            "config": {
                "api_token": "fake-token",      # whatever your integration expects
                "api_url": "https://api.example.com",
            },
        },
    }
```

### Step 6: Write tests

```python
@pytest.mark.asyncio
async def test_resync_creates_expected_entities(
    third_party_transport, mapping_config, integration_config
):
    harness = IntegrationTestHarness(
        integration_path=INTEGRATION_PATH,
        port_mapping_config=mapping_config,
        third_party_transport=third_party_transport,
        config_overrides=integration_config,
    )

    try:
        await harness.start()
        result = await harness.trigger_resync()

        assert len(result.upserted_entities) == 1
        entity = result.upserted_entities[0]
        assert entity["identifier"] == "proj-1"
        assert entity["blueprint"] == "myBlueprint"
        assert entity["properties"]["projectName"] == "My Project"
    finally:
        await harness.shutdown()
```

### Step 7: Run it

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
```
