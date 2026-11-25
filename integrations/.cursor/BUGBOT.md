# Bugbot guidance for Ocean integrations (`integrations/*`)

Integrations sync third-party data into customers' Port catalogs. Bugs here create wrong, duplicated, or deleted entities, or hit customers' API rate limits. These rules add to the root `.cursor/BUGBOT.md`. They apply to every integration, to code the PR adds or changes.

## Validate API-layer changes against the third-party docs

Any new or modified API-layer code (clients, exporters, endpoints, auth, pagination, query params, request bodies, response parsing, rate limiting, webhook payload handling) must match the third party's official documentation. This covers adding new API code, including a brand-new integration, a new endpoint or resource kind, or a new webhook processor, as well as editing existing code. Do not accept "it looks right" or behaviour guessed from other integrations. For each such change, check the code against the docs and flag anything that cannot be confirmed:

- Endpoint path, HTTP method, API version, and base URL.
- Authentication scheme, header names, token type, and the minimum scopes or permissions required.
- Request parameters and body: names, types, required versus optional, and allowed values.
- Response shape: field names, nesting, nullability, date and ID formats, and enum values that the code or mappings depend on.
- Pagination mechanism, page-size maximum, and the documented end-of-results signal.
- Documented rate limits, concurrency limits, and rate-limit headers.
- Webhook event names, payload structure, and signature verification method.

If the PR does not cite or link the relevant documentation, or the code contradicts it, flag it and ask the author to link the doc section that justifies the change. Where docs are ambiguous or undocumented, ask for evidence such as a sample response in `examples/`, and for the assumption to be called out.

## HTTP and third-party API access

- Use core's `http_async_client` (`from port_ocean.utils import http_async_client`) for HTTP. Flag new use of `requests`, `aiohttp`, or a hand-built `httpx.AsyncClient` in non-test code. Third-party SDKs need a clear reason, and they must not be blocking.
- Requests need sensible timeouts and error handling. Check that `raise_for_status()` or the equivalent is not skipped, and that failures are not turned into empty results.
- No blocking calls (`time.sleep`, sync I/O, blocking SDK calls) inside `async` code.
- Handle 401/403 and missing permissions gracefully:
  - Log the endpoint and the missing scope or permission, with a pointer to the fix.
  - Raise a clear custom exception, and let one unmapped or forbidden kind not fail the whole sync where that is safe.
- Check rate-limit handling against the API's documented limits. Use `aiolimiter.AsyncLimiter` for requests per time window and `asyncio.Semaphore` for concurrent limits. Honour `Retry-After` and rate-limit headers. Flag unbounded `asyncio.gather` fan-out against rate-limited APIs.

## Pagination and memory

- All list endpoints must paginate fully and stop on the documented terminator. Check for off-by-one pages, a missing last page, infinite loops when the cursor does not advance, and page-size values above the API's maximum.
- Resync handlers must yield batches (async generators). Flag code that collects a whole resource into a list before yielding.
- Per-item enrichment (an extra API call for every item) needs bounded concurrency and, where the data is shared, caching.

## Minimize API requests

Third-party rate limits are usually the bottleneck, so always flag avoidable requests, and recommend a cheaper alternative where one exists. The developer decides.

- N+1 patterns: a request per item inside a loop over a list when a bulk, batch, list-with-filter, `include`/`expand`, or GraphQL query could return it in fewer calls. Check the API docs for batch endpoints before accepting per-item calls.
- Re-fetching data already in hand: the same resource requested more than once in a resync (for example once per child kind), or fetched again when it was already returned by an earlier call or sits in the payload. Recommend reusing it, passing it down, or caching it (`cache_iterator_result`, `cache_coroutine_result`, or the Ocean cache provider), keyed correctly.
- Fetching more than needed: no field selection or filters when the API supports them, requesting data for kinds the user has not mapped, and optional expensive fetches that are not gated behind a selector flag.
- Pages: page size below the documented maximum when a larger one is allowed, and requesting pages after the end of results.
- Live events: refetching a whole collection to handle one webhook event when the event payload or a single-resource fetch is enough.
- Retries without backoff, or retrying requests that cannot succeed (for example repeated 403/404 responses).

## Structure (apply to code the PR adds or changes)

- `main.py` only wires the Ocean hooks (`@ocean.on_resync`, `@ocean.on_incremental_resync`, `@ocean.on_start`, and webhook registration). It holds no business logic or direct API calls. The same applies to any module that registers these hooks.
- The client layer is generic (authentication, `send_api_request`, `send_paginated_request`, rate limiting, errors). Resource-specific fetching belongs in per-kind exporters. Flag new `get_<resource>()` methods being added to a generic client.
- Model structured data (API options, params, parsed responses, config) with Pydantic models, not raw dicts. See the root file's "Typed models" rule, which applies here in full.
- A new helper or abstraction that is standalone (nothing specific to this third-party system) should be recommended for core instead. See the root file's "Reuse in core" rule.
- Do not instantiate clients per call. Use the integration's existing factory or singleton pattern.
- Config keys read via `ocean.integration_config[...]` must exist in `.port/spec.json` (camelCase there, snake_case in code), and the reverse.

## Webhooks and live events

- `authenticate` must verify the signature or secret per the third party's spec and must not default to returning `True` without a reason.
- `validate_payload` must check exactly the fields that `handle_event` reads with `[]`. Using `.get()` in `handle_event` for fields already validated is a smell, and indexing a field that was never validated is a bug.
- `get_matching_kinds` and `should_process_event` must agree with the events and kinds the mapping supports.
- Register webhook processors with static paths (`ocean.add_webhook_processor("/webhook", ...)`). Dynamic paths are dropped for Redis live events.
- Upsert and delete events must map correctly. A delete event must not upsert, and the reverse.
- Set `saas.liveEvents.enabled` to `true` in `spec.json` only when webhooks are actually implemented.

## `.port/` assets and mapping compatibility

Existing customers have these installed, so changes must stay compatible:

- `spec.json`:
  - Do not rename or remove configuration, features, or kinds that existing users rely on.
  - Secrets need `"sensitive": true`. Config names are camelCase.
  - New required configuration breaks existing installs, so make it optional with a default.
- `blueprints.json` and `port-app-config.yml`:
  - Do not rename blueprint identifiers or properties, or change identifier mappings, without a migration story. That orphans or duplicates entities.
  - Identifiers should come from stable IDs, usually `.id | tostring`, not names or titles that can change.
  - Every `kind` in the mapping must exist in the integration's kind enum and in `spec.json` `features`.
  - Relations and properties in the mapping must exist in `blueprints.json`.
  - JQ must handle missing and null fields without producing bad entities.
- A new or changed resource kind needs sample data in the integration's `examples/` folder and a matching entry in the default mapping and blueprints.
- Selectors (Pydantic models in `integration.py`) must keep their defaults fast. Flags that sharply increase data volume or API calls must default to `False` and be documented.

## Multi-account, caching, and data correctness

- Any cache must be keyed by everything that changes the result (account, org, tenant, region, token). Cached data must never leak across accounts or tenants.
- For multi-account or multi-org integrations, check that identifiers stay unique across accounts and that errors in one account do not abort or corrupt the others.
- Cache decorators (`cache_iterator_result`, `cache_coroutine_result`) must not wrap functions whose results depend on arguments missing from the key.
- Do not return partial data as complete when a request fails midway through pagination.

## Dependencies

- Do not hand-edit an integration's `port_ocean` pin or version for a core-only change. CI and release tooling handle that.
- New third-party dependencies need a clear reason. Flag unpinned or very loosely pinned additions.
