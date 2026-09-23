# Plain Integration — Detailed Implementation Task List

> Branch: `feat/plain-integration`  
> Companion doc: [IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)  
> Rule: **every task ends with tests that must pass before starting the next dependent task.**

## How to use this list

1. Work tasks in order within each phase unless a task explicitly allows parallel work.
2. Do not start a task until all **Prerequisites** are done.
3. After finishing a task, run the **Exit tests** and only then check the box.
4. Prefer Linear-style patterns (`integrations/linear/`) for GraphQL client / resync handlers.

### Status legend

- `[ ]` not started
- `[~]` in progress
- `[x]` done

### Dependency overview (Phase 1)

```text
T0  Verify API assumptions
 │
 ▼
T1  Scaffold integration
 │
 ▼
T2  Utils + exceptions
 │
 ▼
T3  GraphQL client (execute)
 │
 ▼
T4  Relay pagination
 │
 ├──────────────┬──────────────┬──────────────┐
 ▼              ▼              ▼              ▼
T5 company   T6 tenant      T7 user       T8 customer
 │              │              │              │
 └──────────────┴──────┬───────┴──────────────┘
                       ▼
                 T9 thread (+ getters stubs)
                       │
                       ▼
                 T10 blueprints + port-app-config
                       │
                       ▼
                 T11 Phase-2 stubs in spec / on_start
                       │
                       ▼
                 T12 README + changelog + lint gate
```

`T5`–`T8` can run in parallel after `T4`.  
`T9` should start only after `T5`–`T8` are done (so relations/mapping targets exist).  
`T10` can start once `T5`–`T9` queries/fields are stable (may begin earlier as draft, finalize after `T9`).

---

## Phase 1 — Resync MVP

### T0 — Verify Plain API assumptions

**Goal:** Confirm endpoint, auth, page size, list query shapes, and permission names before coding.

**Prerequisites:** none

**Work**
- [ ] Confirm GraphQL URL (`https://core-api.uk.plain.com/graphql/v1` vs regional variants)
- [ ] Confirm Bearer auth with API key
- [ ] Confirm Relay pagination (`first`/`after`, max 100)
- [ ] Confirm list connection paths for: `companies`, `tenants`, `users`, `customers`, `threads`
- [ ] Confirm single-entity queries exist for `thread(id)` / `customer(id)` (Phase 2 stubs)
- [ ] Note exact API key permission names needed

**Exit tests / checks**
- [ ] Document findings in a short `API_NOTES.md` under `integrations/plain/` **or** append an “API verification” section to this file
- [ ] At least one manual `curl`/GraphQL explorer list response captured (sanitized) for `threads` and one other kind

**Done when:** team agrees on URL + auth + pagination + 5 list queries.

---

### T1 — Scaffold `integrations/plain/`

**Goal:** Empty but runnable Ocean integration skeleton.

**Prerequisites:** `T0`

**Work**
- [ ] Create scaffold via Ocean CLI / skill (`ocean new` or create-ocean-integration skill)
- [ ] Ensure package layout exists:
  - `pyproject.toml`, `Makefile`, `debug.py`, `main.py`, `integration.py`
  - `.port/spec.yaml` (or `spec.json`)
  - `.port/resources/` placeholders
  - `tests/` with smoke test
- [ ] Wire `port_ocean` dependency consistent with other integrations
- [ ] Integration identifier/type = `plain`

**Exit tests**
- [ ] `cd integrations/plain && poetry install`
- [ ] `poetry run pytest -q` (scaffold smoke test passes)
- [ ] `make lint` (or project equivalent) passes on scaffold

**Done when:** empty integration installs and tests run.

---

### T2 — Core utils + exceptions

**Goal:** Shared types/helpers used by client and handlers.

**Prerequisites:** `T1`

**Work**
- [ ] `plain/exceptions.py` — `PlainGraphQLError` (and optional HTTP wrapper)
- [ ] `plain/utils.py` — `ObjectKind` enum (`COMPANY`, `TENANT`, `USER`, `CUSTOMER`, `THREAD`)
- [ ] Helpers: `get_nested(data, path)`, `edges_to_nodes(connection)`

**Exit tests** (`tests/test_utils.py`, `tests/test_exceptions.py`)
- [ ] `get_nested` happy path + missing path
- [ ] `edges_to_nodes` flattens Relay edges
- [ ] `ObjectKind` values match intended kind strings (`company`, `tenant`, …)
- [ ] `poetry run pytest tests/test_utils.py tests/test_exceptions.py -q`

**Done when:** utils/exceptions covered by unit tests.

---

### T3 — GraphQL `execute()` client

**Goal:** Authenticated POST that returns `data` and fails on GraphQL/HTTP errors.

**Prerequisites:** `T2`

**Work**
- [ ] `plain/client.py` with `PlainClient`
- [ ] Read `api_token`, `api_url` from `ocean.integration_config`
- [ ] `execute(query, variables, operation_name=None) -> dict`
- [ ] Raise on HTTP errors and on response `errors[]`
- [ ] Set `Authorization: Bearer …`

**Exit tests** (`tests/test_client_execute.py`)
- [ ] Success: mocked 200 with `{ "data": {...} }` returns data
- [ ] GraphQL errors: `{ "errors": [...] }` raises `PlainGraphQLError`
- [ ] HTTP 401/500 raises clearly
- [ ] Auth header is Bearer token from config
- [ ] `poetry run pytest tests/test_client_execute.py -q`

**Done when:** execute path is fully unit-tested with mocks (no live API required).

---

### T4 — Relay pagination helper

**Goal:** Generic multi-page iterator for all list kinds.

**Prerequisites:** `T3`

**Work**
- [ ] `paginate_connection(query, operation_name, variables, connection_path)`
- [ ] Inject `first` / `after` into variables each page
- [ ] Yield batches of nodes
- [ ] Stop when `pageInfo.hasNextPage` is false
- [ ] Honor `page_size` from config (cap at 100)

**Exit tests** (`tests/test_client_pagination.py`)
- [ ] Single page: yields one batch, stops
- [ ] Multi-page: uses `endCursor` as next `after`, yields all pages in order
- [ ] Empty connection: yields nothing / empty batch without hanging
- [ ] Does not request another page when `hasNextPage=false`
- [ ] `poetry run pytest tests/test_client_pagination.py -q`

**Done when:** pagination edge cases are covered; this unblocks all kind work.

---

### T5 — Kind: `company`

**Goal:** List companies end-to-end (query → client method → resync handler).

**Prerequisites:** `T4`  
**Parallel with:** `T6`, `T7`, `T8`

**Work**
- [ ] `LIST_COMPANIES` in `plain/queries.py`
- [ ] `client.get_companies()` using `paginate_connection(..., "data.companies")`
- [ ] `@ocean.on_resync("company")` in `main.py`
- [ ] Register kind in spec exporter resources

**Exit tests** (`tests/test_company.py` and/or client query tests)
- [ ] Query string contains expected fields (`id`, `externalId`, `name`, …)
- [ ] Client method yields nodes from mocked paginated response
- [ ] Resync handler yields batches (unit-test with mocked client)
- [ ] `poetry run pytest -q -k company`

**Done when:** company resync path works under mocks.

---

### T6 — Kind: `tenant`

**Prerequisites:** `T4`  
**Parallel with:** `T5`, `T7`, `T8`

**Work**
- [ ] `LIST_TENANTS` query
- [ ] `client.get_tenants()`
- [ ] `@ocean.on_resync("tenant")`
- [ ] Spec resource registration

**Exit tests**
- [ ] Query field smoke assertions
- [ ] Client pagination mock yields tenants
- [ ] Resync handler mock test
- [ ] `poetry run pytest -q -k tenant`

---

### T7 — Kind: `user`

**Prerequisites:** `T4`  
**Parallel with:** `T5`, `T6`, `T8`

**Work**
- [ ] `LIST_USERS` query
- [ ] `client.get_users()`
- [ ] `@ocean.on_resync("user")`
- [ ] Spec resource registration

**Exit tests**
- [ ] Query/client/resync tests analogous to `T5`
- [ ] `poetry run pytest -q -k user`

---

### T8 — Kind: `customer`

**Prerequisites:** `T4`  
**Parallel with:** `T5`, `T6`, `T7`

**Work**
- [ ] `LIST_CUSTOMERS` query (include `company { id }` and tenants if available)
- [ ] `client.get_customers()`
- [ ] `@ocean.on_resync("customer")`
- [ ] Spec resource registration

**Exit tests**
- [ ] Query includes relation ids needed for mapping
- [ ] Client/resync mock tests
- [ ] `poetry run pytest -q -k customer`

---

### T9 — Kind: `thread` + single-entity getters

**Goal:** Threads list sync + Phase-2-ready getters.

**Prerequisites:** `T5`, `T6`, `T7`, `T8` (relation targets ready)

**Work**
- [ ] `LIST_THREADS` query with customer/tenant/assignee/labels/threadFields
- [ ] Optional `threadStatusFilter` → GraphQL filters variable
- [ ] `client.get_threads()`
- [ ] `@ocean.on_resync("thread")`
- [ ] `GET_THREAD` / `GET_CUSTOMER` queries
- [ ] `client.get_thread(id)` / `client.get_customer(id)` (even if unused in Phase 1)

**Exit tests** (`tests/test_thread.py`, `tests/test_getters.py`)
- [ ] List pagination mock for threads
- [ ] Assignee `__typename` present in fixture for mapping later
- [ ] `get_thread` / `get_customer` return node from mocked response
- [ ] `get_thread` raises on GraphQL errors / missing entity (agreed behavior)
- [ ] Resync handler mock test
- [ ] `poetry run pytest -q -k "thread or getter or get_thread or get_customer"`

**Done when:** all 5 kinds resync under unit tests; getters exist.

---

### T10 — Blueprints + `port-app-config` mappings

**Goal:** Catalog model + JQ mappings for all kinds and relations.

**Prerequisites:** `T9` (fields known). Drafts may start after `T5`–`T8`.

**Work**
- [ ] `.port/resources/blueprints.json` for:
  - `plainCompany`, `plainTenant`, `plainUser`, `plainCustomer`, `plainThread`
- [ ] Relations as in IMPLEMENTATION_PLAN.md
- [ ] `.port/resources/port-app-config.yaml` with mappings
- [ ] `createMissingRelatedEntities: true`
- [ ] Resource order: company → tenant → user → customer → thread

**Exit tests**
- [ ] Mapping smoke tests: given sample raw fixtures, JQ/mapping expectations for identifiers/titles/relations
  - Prefer lightweight tests that validate critical JQ expressions against fixtures in `tests/fixtures/`
- [ ] YAML/JSON parse validation (load files in test)
- [ ] `poetry run pytest -q -k "mapping or blueprint or port_app_config"`

**Done when:** fixtures prove identifiers + key relations resolve.

---

### T11 — Phase 2 stubs (no live webhooks yet)

**Goal:** Spec/config hooks so Phase 2 is non-breaking.

**Prerequisites:** `T1` (can land anytime after scaffold; finalize after `T9`)

**Work**
- [ ] `enableLiveEvents` boolean in `.port/spec.yaml` (default `false`)
- [ ] Guarded `@ocean.on_start` stub that no-ops when disabled
- [ ] Comment or TODO pointing to Phase 2 webhook registration

**Exit tests**
- [ ] Spec loads / config model accepts `enable_live_events`
- [ ] `on_start` does not register webhooks when flag is false
- [ ] `poetry run pytest -q -k "live_events or on_start or spec"`

---

### T12 — Docs, changelog, full gate

**Goal:** Phase 1 merge-ready package on the feature branch.

**Prerequisites:** `T9`, `T10`, `T11`

**Work**
- [ ] README: install config, permissions, kinds, limitations
- [ ] CHANGELOG fragment / entry
- [ ] Example env / debug instructions
- [ ] Ensure `.port/spec` lists all 5 exporter resources

**Exit tests / checks**
- [ ] `poetry run pytest -q` (full suite green)
- [ ] `make lint` / format checks green
- [ ] Manual checklist: no secrets in repo; defaults safe (`enableLiveEvents=false`)

**Phase 1 done when:** full suite + lint pass and docs are reviewable.

---

## Phase 2 — Live events (after Phase 1)

> Do not start Phase 2 until Phase 1 `T12` is complete.

### Dependency overview (Phase 2)

```text
P2-T1 Webhook payload + signature helpers
 │
 ▼
P2-T2 Abstract webhook processor
 │
 ├──────────────────┐
 ▼                  ▼
P2-T3 thread     P2-T4 customer
 processors       processors
 │                  │
 └────────┬─────────┘
          ▼
   P2-T5 webhook registration on_start
          │
          ▼
   P2-T6 docs + full gate
```

### P2-T1 — Payload parsing + signature verification

**Prerequisites:** Phase 1 `T12`, Phase 1 getters (`T9`)

**Work**
- [ ] Parse Plain webhook body into typed structure
- [ ] Verify request signature per Plain docs
- [ ] Reject invalid signatures

**Exit tests**
- [ ] Valid signature accepted
- [ ] Invalid/missing signature rejected
- [ ] Malformed payload rejected
- [ ] `poetry run pytest -q -k "signature or webhook_payload"`

---

### P2-T2 — Abstract Plain webhook processor

**Prerequisites:** `P2-T1`

**Work**
- [ ] `webhook_processors/plain_abstract_webhook_processor.py`
- [ ] Shared validate/authenticate path
- [ ] Register route `/webhook` (or agreed path)

**Exit tests**
- [ ] Base validation unit tests
- [ ] `poetry run pytest -q -k "abstract_webhook or base_webhook"`

---

### P2-T3 — Thread webhook processors

**Prerequisites:** `P2-T2`, Phase 1 `get_thread`

**Work**
- [ ] Handle `thread.created`, `thread.status_transitioned`, `thread.assignment_transitioned`
- [ ] Upsert via `get_thread(id)`

**Exit tests**
- [ ] Each event type → upsert with expected raw result
- [ ] Unknown event ignored
- [ ] `poetry run pytest -q -k "thread_webhook"`

---

### P2-T4 — Customer webhook processors

**Prerequisites:** `P2-T2`, Phase 1 `get_customer`

**Work**
- [ ] Handle `customer.created`, `customer.updated`, `customer.deleted`
- [ ] Upsert/delete accordingly

**Exit tests**
- [ ] Create/update upsert tests
- [ ] Delete removes entity
- [ ] `poetry run pytest -q -k "customer_webhook"`

---

### P2-T5 — Webhook target registration

**Prerequisites:** `P2-T3`, `P2-T4`

**Work**
- [ ] `plain/webhook_setup.py` — create/register webhook target when `enableLiveEvents=true`
- [ ] Wire `@ocean.on_start`
- [ ] Idempotent / safe re-run behavior

**Exit tests**
- [ ] Flag false → no registration calls
- [ ] Flag true → registration called with expected URL/events
- [ ] `poetry run pytest -q -k "webhook_setup or on_start"`

---

### P2-T6 — Phase 2 docs + gate

**Prerequisites:** `P2-T5`

**Work**
- [ ] README live-events section
- [ ] Changelog
- [ ] Full pytest + lint

**Exit tests**
- [ ] `poetry run pytest -q`
- [ ] `make lint`

---

## Phase 3+ backlog (not scheduled)

Only after Phase 2 (or explicitly deferred). Each new kind should follow the same pattern as `T5`–`T9`:

1. Query + client method  
2. Resync handler  
3. Tests for query/client/handler  
4. Blueprint + mapping + mapping fixture test  

Candidates: `machine-user`, `label-type`, `task`, help-center kinds, etc. (see IMPLEMENTATION_PLAN.md).

---

## Definition of done (per task)

A task is done only if:

1. Code for that task is on `feat/plain-integration`
2. **Exit tests** listed above are green
3. No new lint errors in `integrations/plain/`
4. Dependent tasks are not started early (except allowed parallels)

## Suggested first sprint (concrete)

| Day | Tasks |
|-----|-------|
| 1 | `T0`, `T1`, `T2`, start `T3` |
| 2 | Finish `T3`, `T4` |
| 3 | `T5`–`T8` (parallelize if multiple people) |
| 4 | `T9` |
| 5 | `T10`, `T11`, `T12` |

---

## Tracking checkboxes

Copy this into a PR description or project board if useful:

**Phase 1**
- [ ] T0 API verification
- [ ] T1 Scaffold
- [ ] T2 Utils/exceptions + tests
- [ ] T3 Client execute + tests
- [ ] T4 Pagination + tests
- [ ] T5 Company + tests
- [ ] T6 Tenant + tests
- [ ] T7 User + tests
- [ ] T8 Customer + tests
- [ ] T9 Thread + getters + tests
- [ ] T10 Blueprints/mappings + tests
- [ ] T11 Phase-2 stubs + tests
- [ ] T12 Docs/changelog/full gate

**Phase 2**
- [ ] P2-T1 Signature/payload + tests
- [ ] P2-T2 Abstract processor + tests
- [ ] P2-T3 Thread webhooks + tests
- [ ] P2-T4 Customer webhooks + tests
- [ ] P2-T5 Registration + tests
- [ ] P2-T6 Docs/full gate
