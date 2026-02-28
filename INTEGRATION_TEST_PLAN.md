# Integration Test Framework — Feature Plan

## Goal

Create an integration test framework that lets each integration test its full resync pipeline (data fetch → JQ transformation → Port upsert) without depending on real third-party sandbox environments or Port's live API. Tests control both third-party and Port HTTP responses via Python fixtures and assert on the entities produced + error handling behavior.

## Current State

- **Unit tests** — per-integration, mock individual functions/methods
- **Smoke tests** — run the `fake-integration` against a fake Port API server (`fake_port_api.py` on localhost:5555), verify resync completes. No control over third-party responses, no per-integration scenarios
- **Gap** — no way to test an integration's full pipeline with controlled third-party responses, controlled Port mapping config, and assertions on the resulting entities

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│                    Integration Test                       │
│                                                          │
│  1. Define fixtures:                                     │
│     - Third-party API responses (URL → response)         │
│     - Port mapping config (resources/selectors/JQ)       │
│     - Expected entities / expected errors                 │
│                                                          │
│  2. Test harness boots the integration with:             │
│     - InterceptTransport injected into http_async_client │
│     - InterceptTransport injected into Port internal     │
│       client                                             │
│     - Port mapping config provided directly (no API)     │
│                                                          │
│  3. Triggers resync for specific resource kinds          │
│                                                          │
│  4. Collects entities that would be upserted to Port     │
│                                                          │
│  5. Asserts on collected entities + error behavior        │
└──────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Intercept at the HTTPX Transport Layer

Both HTTP clients in the system use `OceanAsyncClient` which wraps `httpx.AsyncClient` with a custom transport via `_init_transport()`:

- **`http_async_client`** (third-party calls) — singleton in `port_ocean/utils/async_http.py`, uses `RetryTransport`
- **Port internal client** — singleton in `port_ocean/clients/port/utils.py`, uses `TokenRetryTransport`

**Approach**: Create an `InterceptTransport` that implements `httpx.AsyncBaseTransport`. It receives a routing table (URL pattern → response) and returns canned responses. For unmatched URLs, it can either raise an error (strict mode) or fall through to a wrapped transport.

This is the cleanest injection point because:
- Both clients already use custom transports — we're just swapping the transport
- No changes to integration code or the core framework's production paths
- httpx's `AsyncBaseTransport` is a stable, well-documented interface
- The `RetryTransport` already wraps a transport — we can slot in underneath it or replace it entirely

### 2. Per-Integration Test Ownership

Each integration owns its test scenarios as Python fixtures. The core provides a thin shared harness (`port_ocean/tests/integration/`) that integrations import.

**Core provides:**
- `InterceptTransport` — the mock transport class
- `IntegrationTestHarness` — boots integration, injects transports, triggers resync, collects results
- `PortMockResponder` — handles standard Port API patterns (auth, blueprints, entity upsert capture, search)
- Helper assertions

**Each integration provides:**
- Python test files in `integrations/{name}/tests/` using pytest
- Fixtures defining third-party response scenarios
- Fixtures defining Port mapping configs (resource configs with JQ)
- Assertions on expected entities and error handling

### 3. Entity Collection via Port Mock

Instead of entities being sent to Port's real API, the `PortMockResponder` captures all upsert calls. Tests can then assert on:
- Which entities were upserted (identifier, blueprint, properties, relations)
- Which entities were deleted
- Which entities failed selector evaluation
- Which JQ mappings produced misconfigurations
- Error handling: how the integration reacted to third-party 429s, 500s, 404s, timeouts

### 4. Resync-Only Scope (Phase 1)

Focus on the resync flow. Webhook/live event testing is a natural extension but not included in this phase.

## Implementation Plan

### Phase 1: Core Harness (`port_ocean/tests/integration/`)

#### 1.1 `InterceptTransport` (`port_ocean/tests/integration/transport.py`)

```python
class InterceptTransport(httpx.AsyncBaseTransport):
    """
    Mock transport that routes requests to canned responses.

    Routes are (method, url_pattern) → response_factory.
    url_pattern can be a string (exact) or regex.
    response_factory can be a static Response, a dict, or a callable(request) → Response.
    """

    def __init__(self, strict: bool = True):
        self._routes: list[Route] = []
        self._call_log: list[RequestLog] = []
        self.strict = strict  # If True, unmatched requests raise error

    def add_route(self, method, url_pattern, response, *, times=None):
        """Register a canned response for a URL pattern."""
        ...

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Match request against routes, return canned response, log the call."""
        ...

    @property
    def calls(self) -> list[RequestLog]:
        """All requests that passed through this transport."""
        ...
```

**Features:**
- URL matching: exact string, regex, or callable predicate
- Response types: static `httpx.Response`, dict (auto-serialized to JSON), or `callable(request) -> response` for dynamic responses
- `times` parameter: route only matches N times, then falls through (for testing pagination, retries)
- Call logging: every request/response pair is logged for assertion
- Strict mode: unmatched requests raise `UnmatchedRequestError` with the URL/method for easy debugging

#### 1.2 `PortMockResponder` (`port_ocean/tests/integration/port_mock.py`)

Pre-configured `InterceptTransport` that handles the standard Port API surface needed during resync:

```python
class PortMockResponder:
    """
    Pre-configured mock for Port API endpoints used during resync.
    Captures upserted entities for assertion.
    """

    def __init__(self, mapping_config: dict, blueprints: dict[str, dict] = None):
        self.transport = InterceptTransport(strict=True)
        self.upserted_entities: list[dict] = []
        self.deleted_entities: list[dict] = []
        self._setup_routes(mapping_config, blueprints)

    def _setup_routes(self, mapping_config, blueprints):
        # POST /v1/auth/access_token → fake token
        # GET/PATCH /v1/integration/{id} → returns mapping_config
        # POST /v1/blueprints/{id}/entities → captures entity, returns success
        # POST /v1/entities/search → returns empty (or configurable)
        # GET/PATCH /v1/blueprints/{id} → returns blueprint schema
        # DELETE /v1/blueprints/{id}/all-entities → returns migration ID
        # GET /v1/migrations/{id} → returns COMPLETE
        # PATCH /v1/integration/{id}/resync-state → OK
        ...
```

This is essentially a programmatic version of the existing `fake_port_api.py`, but injectable as a transport rather than a separate server process.

#### 1.3 `IntegrationTestHarness` (`port_ocean/tests/integration/harness.py`)

The main test driver:

```python
class IntegrationTestHarness:
    """
    Boots an integration with intercepted HTTP transports,
    triggers resync, and collects results.
    """

    def __init__(
        self,
        integration_path: str,
        port_mapping_config: dict,
        third_party_transport: InterceptTransport,
        port_blueprints: dict[str, dict] | None = None,
        config_overrides: dict | None = None,
    ):
        ...

    async def start(self):
        """
        Boot the integration:
        1. Patch http_async_client's transport → third_party_transport
        2. Patch Port internal client's transport → PortMockResponder.transport
        3. Load integration module (main.py with @ocean.on_resync handlers)
        4. Initialize Port app config from provided mapping_config (bypass API)
        """
        ...

    async def trigger_resync(self, kinds: list[str] | None = None) -> ResyncResult:
        """
        Trigger resync for specified kinds (or all).
        Returns collected entities, errors, and metrics.
        """
        ...

    async def shutdown(self):
        """Clean up patched transports and state."""
        ...

@dataclass
class ResyncResult:
    upserted_entities: list[dict]        # Entities sent to Port
    deleted_entities: list[dict]          # Entities marked for deletion
    failed_entities: list[dict]           # Entities that failed selector
    errors: list[Exception]              # Errors during resync
    entity_misconfigurations: dict       # JQ mapping issues
```

**Transport injection strategy:**

The two HTTP client singletons use `LocalStack` + `LocalProxy` for lazy instantiation. The harness will:

1. **For `http_async_client`**: Replace the `_http_client` LocalStack's top entry (or patch `_get_http_client_context`) to return an `OceanAsyncClient` constructed with `InterceptTransport` instead of `RetryTransport`
2. **For Port internal client**: Similarly patch `_port_internal_async_client` / `_get_http_client_context` in `port_ocean/clients/port/utils.py` to return a client with `PortMockResponder`'s transport
3. Both patches are scoped to the test and reverted in `shutdown()`

Alternative: rather than patching module globals, we could make the transport class configurable on `OceanAsyncClient` at construction time — but patching is simpler and avoids modifying production code for testing purposes.

#### 1.4 Pytest Fixtures & Helpers (`port_ocean/tests/integration/fixtures.py`)

```python
@pytest.fixture
async def integration_harness(request):
    """
    Factory fixture that creates an IntegrationTestHarness.
    Usage in integration tests:

        async def test_resync(integration_harness):
            harness = await integration_harness(
                integration_path="./",
                port_mapping_config={...},
                third_party_transport=my_transport,
            )
            result = await harness.trigger_resync()
            assert ...
    """
    ...
```

### Phase 2: Integration-Side Test Pattern

Each integration writes tests like this:

```python
# integrations/github/tests/test_integration.py
import pytest
from port_ocean.tests.integration import (
    InterceptTransport,
    IntegrationTestHarness,
)

@pytest.fixture
def github_transport():
    """Define canned GitHub API responses."""
    transport = InterceptTransport()

    # List repositories
    transport.add_route(
        "GET",
        r"https://api\.github\.com/orgs/.+/repos",
        {
            "status_code": 200,
            "json": [
                {"id": 1, "name": "repo-a", "full_name": "org/repo-a", "private": False},
                {"id": 2, "name": "repo-b", "full_name": "org/repo-b", "private": True},
            ]
        }
    )

    # Simulate rate limit on first call, success on retry
    call_count = {"n": 0}
    def rate_limit_then_succeed(request):
        call_count["n"] += 1
        if call_count["n"] == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(200, json=[{"id": 3, "name": "repo-c"}])

    transport.add_route("GET", r".*/repos/.+/pulls", rate_limit_then_succeed)

    return transport

@pytest.fixture
def github_mapping_config():
    """Port mapping configuration for the test."""
    return {
        "resources": [
            {
                "kind": "repository",
                "selector": {"query": '.private == false'},
                "port": {
                    "entity": {
                        "mappings": {
                            "identifier": ".full_name",
                            "title": ".name",
                            "blueprint": '"githubRepository"',
                            "properties": {
                                "name": ".name",
                                "isPrivate": ".private",
                            }
                        }
                    }
                }
            }
        ]
    }

async def test_resync_filters_private_repos(github_transport, github_mapping_config):
    harness = IntegrationTestHarness(
        integration_path=".",
        port_mapping_config=github_mapping_config,
        third_party_transport=github_transport,
    )
    await harness.start()

    result = await harness.trigger_resync(kinds=["repository"])

    # Only public repos pass the selector
    assert len(result.upserted_entities) == 1
    assert result.upserted_entities[0]["identifier"] == "org/repo-a"
    assert result.upserted_entities[0]["properties"]["isPrivate"] is False

    # Private repo was filtered out by selector
    assert len(result.failed_entities) == 1

    await harness.shutdown()


async def test_rate_limit_recovery(github_transport, github_mapping_config):
    harness = IntegrationTestHarness(
        integration_path=".",
        port_mapping_config=github_mapping_config,
        third_party_transport=github_transport,
    )
    await harness.start()

    result = await harness.trigger_resync(kinds=["pull-request"])

    # Verify the integration retried after 429 and got data
    assert len(result.errors) == 0

    # Verify the 429 request was made (can inspect transport call log)
    rate_limited_calls = [
        c for c in github_transport.calls
        if "pulls" in str(c.url) and c.response.status_code == 429
    ]
    assert len(rate_limited_calls) == 1

    await harness.shutdown()
```

### Phase 3: Pytest Marker & Makefile Integration

#### Pytest Marker

Register a new marker `integration_test` (to distinguish from unit tests and smoke tests):

```python
# pyproject.toml addition
[tool.pytest.ini_options]
markers = [
    "smoke: smoke tests",
    "integration_test: integration tests with mocked HTTP"
]
```

#### Makefile Targets

**Root Makefile:**
```makefile
test/integration:
    $(ACTIVATE) && pytest -m 'integration_test'
```

**Integration Makefile (`_infra/Makefile`):**
```makefile
test/integration:
    $(ACTIVATE) && poetry run pytest -m 'integration_test'
```

## File Structure

```
port_ocean/tests/integration/
├── __init__.py              # Public exports: InterceptTransport, IntegrationTestHarness, etc.
├── transport.py             # InterceptTransport + Route + RequestLog
├── port_mock.py             # PortMockResponder (pre-wired Port API mock)
├── harness.py               # IntegrationTestHarness + ResyncResult
└── fixtures.py              # Shared pytest fixtures

integrations/{name}/tests/
├── test_integration.py      # Integration test scenarios (new)
├── conftest.py              # Integration-specific fixtures (transports, configs)
└── ...                      # Existing unit tests unchanged
```

## Implementation Steps

1. **`InterceptTransport`** — the mock transport with route matching, call logging, strict mode
2. **`PortMockResponder`** — pre-wired Port API mock built on InterceptTransport
3. **`IntegrationTestHarness`** — boots integration, patches transports, triggers resync, collects results
4. **Shared pytest fixtures** — factory fixture for easy test setup
5. **Proof of concept** — write integration tests for `fake-integration` first (simplest case, validates the harness works)
6. **Second integration** — write integration tests for a real integration (e.g., PagerDuty or GitHub) to validate the pattern works with real-world complexity
7. **Makefile + CI** — add `test/integration` targets, add to CI pipeline
8. **Documentation** — add a guide for writing integration tests in `docs/`

## Open Questions / Risks

1. **Multiprocessing in JQ processor**: The `JQEntityProcessor` uses `ProcessPoolExecutor` for CPU-intensive JQ compilation. Forked processes get their own copy of module globals, so the patched transports won't be visible in child processes. We may need to force the sync-path (single-process) during integration tests, or pass transport config through a mechanism that survives fork.

2. **Integration initialization side effects**: Some integrations do work in `@ocean.on_start()` that makes HTTP calls (e.g., validating credentials, setting up webhooks). The `InterceptTransport` needs to handle these too, or the harness needs to provide a way to skip/mock the start phase.

3. **Async generator lifecycle**: The resync flow uses async generators with complex batching. The harness needs to properly drive the full async lifecycle without dropping data or leaving generators unclosed.

4. **Integration config access**: Some integrations read `ocean.integration_config` for settings (API tokens, URLs, etc.). The harness needs to provide mock config values that make sense for the test scenario.

5. **Import side effects**: Loading `main.py` may trigger module-level code. The harness should handle this gracefully.
