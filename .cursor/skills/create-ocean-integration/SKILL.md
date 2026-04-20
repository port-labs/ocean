---
name: create-ocean-integration
description: |
  Build new Ocean integrations that sync third-party API data into Port's software catalog.
  Use when asked to create an integration, add a new data source, build a connector,
  or sync external API data into Port catalog.

  Required argument: integration name (e.g., "Jira", "Datadog", "PagerDuty")
  Optional arguments: task_id (branch name), API base URL, auth type (bearer/api-key/oauth),
  resources to sync, webhook support (yes/no)
---

# Create Ocean Integration

Build production-ready Ocean integrations that sync third-party API data into Port's software catalog.

## Getting Started

When invoking this skill, provide:

**Required:**
- `integration name` - The third-party service to integrate (e.g., "Jira", "Datadog", "PagerDuty")

**Optional (provide if known):**
- `task_id` - Branch name for the work (e.g., "PORT-1234", "feature/datadog-integration", "task_wer3rf3r")
- `API base URL` - The API endpoint (e.g., "https://api.service.com/v1")
- `Auth type` - Authentication method: bearer, api-key, oauth2
- `Resources to sync` - Specific entities to sync (e.g., "projects, issues, users")
- `Webhook support` - Whether to implement live events (yes/no)

**Example invocations:**
- "Create an integration for Datadog"
- "Build a PagerDuty integration with OAuth2 auth, syncing services and incidents"
- "Create a Snyk integration with API key auth at https://api.snyk.io/v1"

## Execution Boundaries

### What You CAN Do Freely (No Approval Needed)

| Action | Examples | Notes |
|--------|----------|-------|
| **Search the web** | Search for API docs, rate limit info, auth methods | Always allowed for evidence gathering |
| **Read third-party docs** | Fetch API reference pages, developer guides | Essential for verification |
| **Read codebase files** | Read, Grep, Glob on existing integrations | Always allowed |
| **Create/modify files** | Write integration code, configs, tests | Within `integrations/{name}/` only |
| **Run lint/format** | `make lint`, `make format`, `black`, `isort`, `ruff` | On created integration only |
| **Auto-fix lint errors** | `black .`, `isort .`, `ruff --fix` | On `integrations/{name}/` only |
| **Run tests** | `make test` on the integration | Always allowed |
| **Create feature branch** | `git checkout -b {task_id}` or `feature/{integration}` | Use task_id if provided, else feature/{integration} |
| **Commit changes** | `git commit` to feature branch | Never to main |

### What Requires Approval (Ask First)

| Action | Why | How to Ask |
|--------|-----|------------|
| **Push to remote** | Could affect CI/CD, others' work | "Ready to push. Should I push to origin?" |
| **Create PR** | Requires review process | "Implementation complete. Should I create a PR?" |
| **Modify shared code** | Could break other integrations | "This requires changing `port_ocean/...`. Proceed?" |
| **Add new dependencies** | Affects package size, security | "Need to add `aiolimiter`. Approve adding dependency?" |
| **Run integration locally** | May require credentials, env setup | "Ready to test locally. Do you have credentials configured?" |
| **Delete files/branches** | Could lose work | "Should I delete the old implementation?" |

### What You CANNOT Do (Forbidden)

| Action | Why |
|--------|-----|
| Push to main/master | Could break production |
| Force push | Could lose work |
| Commit secrets/credentials | Security risk |
| Modify `.env` files | Contains secrets |
| Run against production APIs without permission | Could affect data |

If a task requires a forbidden action, **STOP** and report:

```
BLOCKED: This requires {action} which is not allowed. 
Please {alternative approach}.
```

## Data Flow Overview

Understand how data moves through the integration:

```
┌─────────────────┐
│ 1. THIRD-PARTY  │  API docs, auth, rate limits
│    API          │
└────────┬────────┘
         │ HTTP requests (paginated, rate-limited)
         ▼
┌─────────────────┐
│ 2. CLIENT       │  Auth headers, pagination, error handling
│    LAYER        │
└────────┬────────┘
         │ Raw API responses
         ▼
┌─────────────────┐
│ 3. EXPORTER     │  Resource fetching, enrichment
│    LAYER        │
└────────┬────────┘
         │ Yields batches of raw items
         ▼
┌─────────────────┐
│ 4. OCEAN        │  @ocean.on_resync handlers
│    FRAMEWORK    │
└────────┬────────┘
         │ Applies JQ mappings from port-app-config
         ▼
┌─────────────────┐
│ 5. PORT         │  Entities created/updated
│    CATALOG      │
└─────────────────┘
```

When debugging, trace issues through this flow: Is the API returning data? Is the client parsing it? Is the exporter yielding it? Is the mapping correct?

## Critical: Do Not Assume, Verify

Before writing any code, gather evidence from authoritative sources. Guessing leads to incorrect implementations.

### What to Verify vs What to Assume

| Category | DO NOT Assume | DO Verify From Third-Party Docs |
|----------|---------------|----------------------------------|
| **API Base URL** | URL format or versioning | Exact base URL, API version path |
| **Authentication** | Auth header format, token type | Auth method (Bearer, API key header name, OAuth flow) |
| **Pagination** | Cursor vs offset, param names | Pagination mechanism, page size limits, next page indicator |
| **Rate Limits** | Request limits, concurrent calls | Requests/minute, burst limits, rate limit headers |
| **Response Shape** | Field names, nesting structure | Exact JSON response structure from API reference |
| **Webhook Events** | Event names, payload format | Available event types, webhook signature verification |
| **Permissions** | Required scopes | Minimum scopes needed (least privilege) |
| **Data Types** | Date formats, enums | Exact formats (ISO8601, epoch ms), enum values |

### Evidence Gathering Flow

1. **Locate Official API Documentation**
   - Search for `{service_name} API documentation` or `{service_name} developer docs`
   - Find the REST/GraphQL API reference
   - Identify authentication documentation
   - Locate rate limiting documentation
   - Find webhook/events documentation if applicable

2. **Document API Characteristics**
   Create a notes file with:
   ```markdown
   ## API Evidence for {ServiceName}
   
   ### Authentication
   - Method: {Bearer token | API key header | OAuth2}
   - Header: {Authorization: Bearer | X-API-Key | custom}
   - Source: {link to auth docs}
   
   ### Pagination
   - Type: {offset | cursor | page-based | link-header}
   - Page size param: {limit | per_page | pageSize}
   - Max page size: {number}
   - Next indicator: {hasNextPage | Link header | afterKey}
   - Source: {link to pagination docs}
   
   ### Rate Limits
   - Overall: {X requests per minute/hour}
   - Concurrent: {Y simultaneous requests}
   - Headers: {X-RateLimit-Remaining | Retry-After}
   - Source: {link to rate limit docs}
   
   ### Resources to Sync
   - {resource1}: GET /endpoint - {description}
   - {resource2}: GET /endpoint - {description}
   
   ### Permissions / Scopes
   - Minimum required: {list scopes for OOTB functionality}
   - Optional for {feature}: {additional scope}
   - Source: {link to permissions docs}
   
   ### Webhook Event Mapping
   | Event Type | Maps to Kind | Action |
   |------------|--------------|--------|
   | project.created | project | upsert |
   | project.deleted | project | delete |
   | issue.updated | issue | upsert |
   ```

3. **Verify with Actual API Calls**
   If possible, make test API calls to confirm response shapes match documentation.

## Phase 1: Resource Discovery

### Step 1.1: Identify Resources

For each potential resource, answer:

1. **What entities exist in this third-party system?**
   - Core entities (users, projects, repositories)
   - Child entities (issues, findings, scan results)
   - Configuration entities (settings, environments)

2. **What is the resource hierarchy?**
   - Parent-child relationships (org → repo → PR)
   - Dependencies (scan → scan-results)

3. **Which resources provide value for Port's software catalog?**
   - Does it represent a deployable/service?
   - Does it represent infrastructure?
   - Does it represent a security finding?
   - Does it represent a team/ownership structure?

### Step 1.2: Define Resource Kinds

Create an `ObjectKind` enum with kebab-case string values:

```python
class ObjectKind(StrEnum):
    PROJECT = "project"
    SCAN = "scan"
    FINDING = "finding"
    SCAN_RESULT = "scan-result"
    CODE_SCANNING_ALERT = "code-scanning-alert"
```

Naming conventions:
- Use kebab-case for kind strings
- Singular form (not plurals)
- Match third-party terminology where sensible

## Phase 2: Architecture Design

### Step 2.1: Directory Structure

```
integrations/{integration-name}/
├── main.py                    # Ocean hooks: @ocean.on_resync, @ocean.on_start
├── integration.py             # Pydantic configs, selectors, integration class
├── debug.py                   # Local dev entry: from port_ocean import run
├── pyproject.toml             # Poetry project, port_ocean dependency
├── {integration_name}/        # Main package (snake_case)
│   ├── __init__.py
│   ├── clients/
│   │   ├── __init__.py
│   │   ├── client_factory.py  # Singleton factory
│   │   ├── http/
│   │   │   ├── __init__.py
│   │   │   ├── base_client.py # ABC with pagination, error handling
│   │   │   └── {name}_client.py
│   │   └── auth/
│   │       ├── __init__.py
│   │       ├── abstract_authenticator.py
│   │       └── {method}_authenticator.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── options.py         # TypedDicts for API call options
│   │   └── exporters/
│   │       ├── __init__.py
│   │       ├── abstract_exporter.py
│   │       └── {resource}_exporter.py  # One per resource kind
│   ├── helpers/
│   │   ├── __init__.py
│   │   ├── utils.py           # ObjectKind enum, utilities
│   │   └── exceptions.py      # Custom exceptions
│   └── webhook/               # If live events supported
│       ├── __init__.py
│       ├── events.py          # Event type enums
│       ├── registry.py        # Processor registration
│       └── webhook_processors/
│           ├── __init__.py
│           ├── abstract_webhook_processor.py
│           └── {resource}_webhook_processor.py
├── examples/                  # Sample API responses for testing/docs
│   └── {kind}/
│       └── a.json
├── .port/
│   ├── spec.yaml              # Integration metadata, configs, features
│   └── resources/
│       ├── blueprints.json    # Default Port blueprints
│       ├── port-app-config.yml # Default mappings
│       └── .gitignore
└── tests/
    └── (mirrors source structure)
```

### Step 2.2: Separation of Concerns

| Layer | Responsibility | Example |
|-------|---------------|---------|
| `main.py` | Ocean event wiring only | `@ocean.on_resync(ObjectKind.X)` handlers |
| `integration.py` | Configuration schemas | Pydantic models, selectors, integration class |
| `clients/` | HTTP communication | Auth, pagination, error handling |
| `core/exporters/` | Data fetching logic | One exporter per resource kind |
| `helpers/` | Shared utilities | Enums, exceptions, enrichment functions |
| `webhook/` | Live event processing | Signature validation, event routing |

### Step 2.3: OOP Patterns (MANDATORY)

**THIS IS NOT OPTIONAL.** The following patterns MUST be implemented. Do not create a monolithic client class.

#### What Goes WHERE (Critical)

| Component | SHOULD Contain | SHOULD NOT Contain |
|-----------|---------------|-------------------|
| **Client** (`clients/http/`) | `send_api_request()`, `send_paginated_request()`, rate limiting, error handling | `get_projects()`, `get_tasks()`, `get_users()` - NO resource methods |
| **Exporter** (`core/exporters/`) | `get_paginated_resources()`, `get_single_resource()`, resource-specific logic | HTTP implementation, auth headers, rate limiting |
| **main.py** | `@ocean.on_resync` handlers calling exporters | Business logic, direct API calls, client instantiation |

#### Anti-Patterns to AVOID

```python
# WRONG: Client has resource-specific methods (get_projects, get_issues, etc.)
class ServiceClient(BaseClient):
    async def send_api_request(self, endpoint): ...  # OK
    async def send_paginated_request(self, endpoint): ...  # OK
    
    # WRONG - These belong in EXPORTERS, not client:
    async def get_projects(self): ...  # MOVE TO ProjectExporter
    async def get_issues(self, project_id): ...  # MOVE TO IssueExporter
    async def get_users(self): ...  # MOVE TO UserExporter
    async def get_repositories(self, org_id): ...  # MOVE TO RepositoryExporter
```

```python
# WRONG: main.py calling client methods directly
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str):
    client = ClientFactory.get_client()
    projects = await client.get_projects()  # WRONG - client shouldn't have this
    yield projects
```

#### CORRECT Pattern: Client is Generic, Exporter is Specific

```python
# CORRECT: Client ONLY has generic HTTP methods
class ServiceClient(BaseClient):
    async def send_api_request(self, endpoint: str, method: str = "GET", **kwargs):
        """Generic HTTP request - no resource-specific logic."""
        ...
    
    async def send_paginated_request(self, endpoint: str, **kwargs):
        """Generic pagination - no resource-specific logic."""
        ...
    
    # NO get_projects(), get_issues(), get_users() methods here!
```

```python
# CORRECT: Exporter uses client's generic methods for specific resources
class ProjectExporter(AbstractExporter[ServiceClient]):
    async def get_paginated_resources(self, org_id: str) -> AsyncGenerator:
        # Exporter knows the endpoint and data_key, client doesn't
        async for batch in self.client.send_paginated_request(
            f"orgs/{org_id}/projects",
            params={"state": "all"},
            data_key="projects"
        ):
            yield batch
    
    async def get_single_resource(self, project_id: str) -> dict | None:
        data = await self.client.send_api_request(f"projects/{project_id}")
        return data if data else None
```

```python
# CORRECT: main.py uses exporter, not client directly
@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str):
    client = ClientFactory.get_client()
    exporter = ProjectExporter(client)
    
    for org in await get_organizations():
        async for batch in exporter.get_paginated_resources(org["id"]):
            yield batch
```

#### Required Pattern 1: Abstract Exporter

**File:** `{integration}/core/exporters/abstract_exporter.py`

```python
from abc import ABC, abstractmethod
from typing import Generic, TypeVar, AsyncGenerator, Optional
from port_ocean.core.ocean_types import RAW_ITEM

T = TypeVar("T")  # Client type

class AbstractExporter(ABC, Generic[T]):
    def __init__(self, client: T) -> None:
        self.client = client
    
    @abstractmethod
    async def get_paginated_resources(
        self, **options
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        """Yield batches of resources."""
        pass
    
    @abstractmethod
    async def get_single_resource(self, resource_id: str) -> Optional[RAW_ITEM]:
        """Fetch a single resource by ID."""
        pass
```

#### Required Pattern 2: Concrete Exporters (One Per Kind)

**File:** `{integration}/core/exporters/project_exporter.py`

```python
from typing import AsyncGenerator, Optional
from port_ocean.core.ocean_types import RAW_ITEM

from {integration}.core.exporters.abstract_exporter import AbstractExporter
from {integration}.clients.http.{name}_client import ServiceClient

class ProjectExporter(AbstractExporter[ServiceClient]):
    async def get_paginated_resources(
        self, include_archived: bool = False
    ) -> AsyncGenerator[list[RAW_ITEM], None]:
        async for batch in self.client.send_paginated_request(
            "/projects", params={"archived": include_archived}
        ):
            yield batch
    
    async def get_single_resource(self, resource_id: str) -> Optional[RAW_ITEM]:
        return await self.client.send_api_request(f"/projects/{resource_id}")
```

#### Required Pattern 3: Client Factory

**File:** `{integration}/clients/client_factory.py`

```python
from typing import TypeVar, Type
from functools import lru_cache

from port_ocean.context.ocean import ocean
from {integration}.clients.http.{name}_client import ServiceClient

T = TypeVar("T")

class ClientFactory:
    _instances: dict[Type, object] = {}
    
    @classmethod
    def get_client(cls) -> ServiceClient:
        if ServiceClient not in cls._instances:
            # Config keys come from spec.yaml (camelCase there, snake_case here)
            # Example: serviceUrl in spec.yaml -> ocean.integration_config["service_url"]
            cls._instances[ServiceClient] = ServiceClient(
                base_url=ocean.integration_config["service_url"],
                api_token=ocean.integration_config["service_token"],
            )
        return cls._instances[ServiceClient]
    
    @classmethod
    def clear(cls) -> None:
        cls._instances.clear()
```

#### Required Pattern 4: Base HTTP Client (Generic Only)

**File:** `{integration}/clients/http/base_client.py`

**CRITICAL:** The client class should ONLY have these generic methods. NO `get_projects()`, `get_tasks()`, etc.

```python
from abc import ABC, abstractmethod
from typing import Any, AsyncGenerator
from aiolimiter import AsyncLimiter

class BaseClient(ABC):
    """
    Base HTTP client - GENERIC ONLY.
    
    This class handles:
    - HTTP request sending
    - Rate limiting
    - Error handling
    - Pagination mechanics
    
    This class does NOT handle:
    - Resource-specific endpoints (use Exporters)
    - Data transformation (use Exporters)
    - Business logic (use Exporters)
    """
    
    PAGE_SIZE = 100
    
    def __init__(self, base_url: str, rate_limit_per_minute: int = 100) -> None:
        self.base_url = base_url.rstrip("/")
        self.rate_limiter = AsyncLimiter(rate_limit_per_minute, 60)
    
    @abstractmethod
    async def send_api_request(
        self, endpoint: str, method: str = "GET", **kwargs
    ) -> dict[str, Any]:
        """Send a generic HTTP request. Endpoint is passed by exporter."""
        pass
    
    @abstractmethod
    async def send_paginated_request(
        self, endpoint: str, **kwargs
    ) -> AsyncGenerator[list[dict[str, Any]], None]:
        """Handle pagination. Endpoint is passed by exporter."""
        pass
    
    # DO NOT ADD: get_workspaces(), get_projects(), get_tasks(), etc.
    # Those belong in EXPORTERS, not here.
```

#### Required Pattern 5: Correct main.py Structure

```python
# CORRECT: main.py uses factory and exporters
from {integration}.clients.client_factory import ClientFactory
from {integration}.core.exporters.project_exporter import ProjectExporter

@ocean.on_resync(ObjectKind.PROJECT)
async def on_resync_projects(kind: str) -> ASYNC_GENERATOR_RESYNC_TYPE:
    client = ClientFactory.get_client()
    exporter = ProjectExporter(client)
    
    async for batch in exporter.get_paginated_resources():
        yield batch
```

#### Checklist Before Proceeding

**STOP and verify this structure before writing any implementation code:**

- [ ] `clients/client_factory.py` exists with singleton pattern
- [ ] `clients/http/base_client.py` exists as ABC with ONLY generic methods
- [ ] `clients/http/{name}_client.py` extends BaseClient
- [ ] **Client has NO `get_X()` methods** - Only `send_api_request()` and `send_paginated_request()`
- [ ] `core/exporters/abstract_exporter.py` exists as ABC
- [ ] One exporter file per ObjectKind in `core/exporters/`
- [ ] **Exporters call `self.client.send_api_request(endpoint)`** - NOT `self.client.get_resources()`
- [ ] `main.py` ONLY wires handlers, uses factory + exporters
- [ ] No resource fetching logic in main.py

**If adding a new resource type:** Create a new exporter file, NOT a new method on the client.

### Step 2.4: Decision Framework

**Document your decision:**

```markdown
**Decision:** Use cursor pagination + cache projects

**Rationale:**
- API returns `afterKey` in responses (cursor-based)
- Rate limit is 100 req/min, caching projects avoids re-fetching

**Trade-offs accepted:**
- Cannot parallelize pagination (cursor is sequential)
```

## Phase 3: Implementation

### Step 3.0: Bootstrap with `make new`

Always bootstrap new integrations using `make new` from the ocean repo root. This ensures consistent structure.

**The command is interactive and requires user input:**

```bash
cd /path/to/ocean
make new
```

**Prompts you'll need to answer (10 total):**

| # | Prompt | Example Value | Notes |
|---|--------|---------------|-------|
| 1 | `integration_name` | `datadog` | lowercase, kebab-case for multi-word |
| 2 | `integration_slug` | `datadog` | Usually same as name |
| 3 | `integration_short_description` | `Datadog integration for Port Ocean` | Brief description |
| 4 | `full_name` | `Your Name` | Author name |
| 5 | `email` | `you@example.com` | Author email |
| 6 | `release_date` | `{today's date}` | Default is current date |
| 7 | `is_private_integration` | `n` | Usually `n` for public integrations |
| 8 | `port_client_id` | `{your_client_id}` | From Port credentials |
| 9 | `port_client_secret` | `{your_client_secret}` | From Port credentials |
| 10 | `is_us_region` | `n` | `y` if using US region |

**How to handle this:**

Always escalate to the user because:
- The command requires Port credentials (client_id, client_secret)
- Interactive prompts may not work with piped input
- User should verify the inputs are correct

```
ACTION REQUIRED: Please run `make new` in the ocean repo root.

cd /path/to/ocean
make new

Suggested inputs:
1. integration_name: {name}
2. integration_slug: {name}
3. integration_short_description: {Name} integration for Port Ocean
4. full_name: {your name}
5. email: {your email}
6. release_date: {press Enter for default}
7. is_private_integration: n
8. port_client_id: {your Port client ID}
9. port_client_secret: {your Port client secret}
10. is_us_region: n (or y if US region)

After completion, run:
cd integrations/{name} && make install && . .venv/bin/activate

Let me know when complete, and I'll continue building the integration.
```

**After bootstrapping:**

The generated structure at `integrations/{name}/` includes:
- `main.py` - Empty handlers to fill in
- `integration.py` - Base integration class
- `pyproject.toml` - Dependencies (add `aiolimiter` here)
- `.port/spec.yaml` - Metadata to customize
- `.port/resources/` - Blueprints and mappings to create

Continue from this generated scaffold rather than creating files from scratch.

### Step 3.1: Client Implementation

```python
class BaseClient(ABC):
    PAGE_SIZE = 100  # From API docs, not assumed
    
    def __init__(self, base_url: str, authenticator: AbstractAuthenticator):
        self.base_url = base_url.rstrip("/")
        self.authenticator = authenticator
    
    async def send_api_request(
        self,
        endpoint: str,
        method: str = "GET",
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None,
        ignored_errors: Optional[List[IgnoredError]] = None,
    ) -> Dict[str, Any]:
        # Implementation with error handling
        pass
    
    async def send_paginated_request(
        self,
        endpoint: str,
        params: Optional[Dict] = None,
    ) -> AsyncGenerator[List[Dict[str, Any]], None]:
        # Pagination implementation per API docs
        pass
```

### Step 3.2: Exporter Implementation

```python
class AbstractExporter(ABC, Generic[T]):
    def __init__(self, client: T):
        self.client = client
    
    @abstractmethod
    async def get_paginated_resources(
        self, options: Optional[Dict] = None
    ) -> AsyncGenerator[List[RAW_ITEM], None]:
        pass
    
    @abstractmethod
    async def get_resource(self, resource_id: str) -> Optional[RAW_ITEM]:
        pass
```

### Step 3.2.1: Permission Error Handling

Implement clear, actionable error messages when permissions are insufficient:

```python
class MissingScopeError(Exception):
    """Raised when API returns 403 due to missing permissions."""
    pass

async def send_api_request(self, endpoint: str, ...) -> Dict[str, Any]:
    response = await self._http_client.request(...)
    
    if response.status_code == 403:
        # Log actionable error message
        logger.error(
            f"Permission denied for {endpoint}. "
            f"Ensure your API token has the '{self._get_required_scope(endpoint)}' scope. "
            f"See {self._docs_url}/permissions for required permissions."
        )
        raise MissingScopeError(
            f"Missing permission for {endpoint}. "
            f"Required scope: {self._get_required_scope(endpoint)}"
        )
```

**Key principles:**
- Log the specific endpoint that failed
- State which permission/scope is missing
- Link to documentation on how to fix it
- Allow graceful degradation: if user hasn't mapped a kind, don't fail the entire sync

### Step 3.3: Rate Limiting Decisions

**Prefer `aiolimiter` library** for rate limiting. Only implement custom rate limiters for special cases.

**Distinguish concurrent vs overall limits:**

| Limit Type | What It Means | Implementation |
|------------|---------------|----------------|
| **Concurrent** | Max simultaneous requests (e.g., 10 at once) | `asyncio.Semaphore(max_concurrent)` |
| **Overall** | Requests per time window (e.g., 1000/min) | `aiolimiter.AsyncLimiter(requests, seconds)` |

**Decision Framework:**

| API Characteristic | Implementation |
|--------------------|----------------|
| Known requests/second or requests/minute | `aiolimiter.AsyncLimiter` |
| Concurrent request limits | `asyncio.Semaphore` |
| Both rate and concurrent limits | Combine `AsyncLimiter` + `Semaphore` |
| API returns rate limit headers to track | Custom header-based limiter (see references) |
| No documented limits | Start with Ocean defaults, add if issues arise |

**Impact on caching and speed:**

- **Tight rate limits** → Cache parent resources (projects, repos) to avoid re-fetching during child iteration
- **Low concurrent limits** → Reduce parallelism in `asyncio.gather()` calls
- **Per-endpoint limits** → Use separate semaphores per endpoint type
- **Expensive enrichment calls** → Consider `@cache_iterator_result()` decorator

For detailed rate limiting patterns, see [references/rate-limiting-patterns.md](references/rate-limiting-patterns.md).

### Step 3.4: Pagination Patterns

Choose the appropriate pagination pattern based on API documentation.

For detailed pagination implementations, see [references/pagination-patterns.md](references/pagination-patterns.md).

### Step 3.5: Webhook Implementation

Only implement if the third-party supports webhooks:

1. **Check third-party webhook docs for:**
   - Available event types
   - Webhook signature verification method
   - Payload structure

2. **Register processors in main.py:**
   ```python
   ocean.add_webhook_processor("/webhook", ResourceWebhookProcessor)
   ```

For detailed webhook patterns, see [references/webhook-patterns.md](references/webhook-patterns.md).

## Phase 4: Port Configuration (.port directory)

### What Goes in .port/ (Provisioned by Default)

The `.port/` directory contains configurations that are **automatically provisioned** when the integration is installed.

| File | Purpose | Provisioned? |
|------|---------|--------------|
| `spec.yaml` | Integration metadata, config fields, features | Yes (required) |
| `resources/blueprints.json` | Default blueprint definitions | Yes |
| `resources/port-app-config.yml` | Default resource mappings | Yes |

Note: Examples live in `{integration_name}/examples/`, NOT in `.port/`.

### Step 4.1: spec.yaml Structure

```yaml
title: {Service Name}
description: {Service name} integration for Port Ocean
icon: {IconName}
docs: https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/{category}/{integration}
features:
  - type: exporter
    section: {Category}  # e.g., Security, Git Providers, Cloud
    resources:
      - kind: {kind-1}
      - kind: {kind-2}
configurations:
  - name: {serviceName}BaseUrl  # camelCase
    required: false
    default: https://api.service.com
    type: url
    description: Base URL for the API
  - name: {serviceName}ApiKey
    required: true
    type: string
    sensitive: true
    description: API key for authentication
saas:
  enabled: true
  liveEvents:
    enabled: {true if webhooks implemented}
```

### Step 4.2: Selectors and BaseModels per Kind

Define Pydantic selectors in `integration.py` to give users control without hurting OOTB performance:

```python
class ProjectSelector(BaseModel):
    include_archived: bool = Field(
        default=False,
        description="Include archived projects (increases data volume)"
    )
    include_statistics: bool = Field(
        default=False,
        description="Fetch detailed statistics per project (slower, more API calls)"
    )

class ResourceSelector(BaseModel):
    projects: ProjectSelector = Field(default_factory=ProjectSelector)
    issues: IssueSelector = Field(default_factory=IssueSelector)
```

**Design principles:**
- **OOTB defaults should be fast** - Flags that 10x data volume default to `False`
- **Document impact** - Describe what each flag does and its performance cost
- **Expose in spec.yaml** - Make selectors configurable via integration config
- **Use in exporters** - Pass selector options to `get_paginated_resources()`

Example usage in exporter:
```python
async def get_paginated_resources(self, options: ProjectSelector) -> AsyncGenerator:
    params = {"archived": options.include_archived}
    if options.include_statistics:
        # Additional API call per project
        ...
```

### Step 4.3: Blueprint Design

For detailed blueprint design patterns, see [references/blueprint-design.md](references/blueprint-design.md).

Key decisions:
- Only include OOTB-valuable properties
- Use `enum` with `enumColors` for status fields
- Define relations that establish hierarchy (child → parent)
- Use stable, unique identifiers from API (IDs, not names)

### Step 4.4: Mapping Design

```yaml
deleteDependentEntities: true
createMissingRelatedEntities: true
resources:
  - kind: {kind}
    selector:
      query: 'true'
    port:
      entity:
        mappings:
          identifier: .id | tostring
          title: .name
          blueprint: '"{blueprintIdentifier}"'
          properties:
            # Map API response fields to blueprint properties
          relations:
            # Map to related entities
```

### Step 4.5: Examples Directory

Place sample API responses in `{integration_name}/examples/{kind}/`:
- Used for testing mappings
- Documents expected API response shape
- NOT provisioned to users (lives outside `.port/`)
- Name files `a.json`, `b.json`, etc. for multiple samples

## Phase 5: Documentation Planning

**Create a docs PR in `port-docs` repo alongside the integration PR.**

Documentation should cover:

1. **Prerequisites**
   - Required permissions/scopes (least privilege principle)
   - API access requirements
   - How to obtain credentials (step-by-step)

2. **Configuration**
   - Each config field from spec.yaml with description
   - Example values
   - Sensitive field handling

3. **Supported Resources**
   - Each kind with description
   - Default blueprint properties
   - Selector options and their effects on data volume/performance

4. **Webhooks** (if applicable)
   - How to configure webhook URL in third-party system
   - Supported events and which kinds they affect
   - Signature verification requirements

5. **Troubleshooting**
   - Common permission errors and how to fix them
   - Rate limit guidance

## Quality Checklist

Before finalizing:

**OOP Structure (MANDATORY - verify first):**
- [ ] `clients/client_factory.py` exists with singleton pattern
- [ ] `clients/http/base_client.py` exists as ABC
- [ ] `clients/http/{name}_client.py` extends BaseClient
- [ ] **Client ONLY has generic methods:** `send_api_request()`, `send_paginated_request()`
- [ ] **Client has NO resource methods:** No `get_workspaces()`, `get_tasks()`, `get_users()`, etc.
- [ ] `core/exporters/abstract_exporter.py` exists as ABC
- [ ] One exporter file exists per ObjectKind in `core/exporters/`
- [ ] **Exporters call client's generic methods** with specific endpoints
- [ ] `main.py` ONLY contains @ocean handlers, no business logic
- [ ] `main.py` uses ClientFactory + Exporters, not direct client methods

**API & Data:**
- [ ] All API endpoints verified against official docs
- [ ] Pagination matches documented behavior
- [ ] Rate limiting configured per API limits (concurrent vs overall distinguished)
- [ ] Caching strategy defined for rate-limited resources
- [ ] Authentication uses exact documented method
- [ ] No assumed field names (all verified)
- [ ] Error handling for documented error codes

**Webhooks:**
- [ ] Webhook events mapped to kinds with upsert/delete actions
- [ ] Webhook signatures verified per third-party spec

**Configuration:**
- [ ] Permissions follow least privilege
- [ ] Permission errors are clear and actionable (log scope needed, link to docs)
- [ ] Selectors defined per kind with optional flags documented
- [ ] OOTB defaults are fast (expensive flags default to False)
- [ ] Blueprint properties represent OOTB value

**Testing & Docs:**
- [ ] Tests cover pagination edge cases
- [ ] Docs PR created in port-docs with prerequisites, config, resources, troubleshooting

## Reference: Gold Standard Patterns

### From GitHub Integration
- Multiple auth strategies (PAT, GitHub App)
- GraphQL + REST clients
- Custom rate limiter with header tracking
- Rich webhook ecosystem with group processing
- `@cache_iterator_result()` for expensive pagination

### From Okta Integration
- Webhook verification challenge (GET handler)
- User enrichment with nested pagination (groups, apps)
- Simple two-resource design

### From Checkmarx-One Integration
- OAuth token caching in Ocean cache provider
- Multiple pagination strategies (offset, cursor, page-based)
- Scan-result pattern (parent scan → child results)

### From Armorcode Integration
- Minimal viable integration (3 kinds, no webhooks)
- Clean offset vs cursor pagination switch
- Good example of simple client hierarchy
