# Bugbot guidance for the Ocean framework (`port_ocean/`)

Every integration runs on this code. Treat a small framework change as a change to ~50 products. These rules add to the root `.cursor/BUGBOT.md`.

## Backward compatibility (highest priority)

Flag any change that can break an existing integration without that integration being edited:

- Changed, renamed, or removed public APIs: the `ocean` context, `ocean.on_resync`/`on_start`/webhook registration, integration base classes, `AbstractWebhookProcessor`, `PortAppConfig`, `ResourceConfig`, `Selector`, and exported helpers in `port_ocean/utils/`.
- New abstract methods, new required constructor arguments, or new required config on classes integrations subclass or instantiate.
- Changed defaults or semantics of existing settings, or renamed settings and environment variables.
- Changes to what is sent to or expected from Port's API that are not compatible with the deployed Port API schema.
- Behavioural changes to defaults that existing installations rely on (for example mapping defaults, `deleteDependentEntities`, and `createMissingRelatedEntities` behaviour).

If the change is intentional, the PR needs a breaking-change release intent and a migration path or deprecation.

## Resync data safety

Resync decides what to create, update, and delete in a customer's catalog. Be strict here (`core/integrations/mixins/sync_raw.py` and related handlers):

- The delete/unregister phase must be skipped or aborted when registration or calculation had errors. Flag anything that deletes after partial failure.
- Do not swallow, downgrade, or drop errors from `gather_and_split_errors_from_results` or per-kind tasks. A failed kind must not look like "no entities".
- An empty result caused by an error, a timeout, or an aborted request must not be treated as "the source has no data".
- Keep abort handling intact: `OceanAbortException`, `event.on_abort`, and cancellation. Do not swallow `asyncio.CancelledError`.
- Be careful with ordering and relations: entities that fail to upsert are retried via topological sort, so do not break that fallback.

## Normal mode and DSP/lakehouse mode

Ingestion has more than one path (for example the lakehouse buffer and DSP). When changing `sync_raw`, `live_events`, `register_raw`, entity appliers, or Port clients, check that every path still behaves correctly. A recent bug was `register_raw` bypassing lakehouse ingestion in DSP mode. Those files are co-owned by the lighthouse team, so call out cross-path effects explicitly.

## Async, memory, and performance

- No blocking I/O or `time.sleep` inside `async` code paths. Use async equivalents or run blocking work off the event loop.
- Do not materialise whole async generators or large datasets into lists in resync or live-event paths. Keep yielding batches.
- Unbounded concurrency (`asyncio.gather` over an unbounded collection, unbounded queues) needs a limit or semaphore. Prefer the existing helpers in `port_ocean/utils/async_iterators.py` and `queue_utils.py`.
- New caches need a bounded size or lifetime and a correct key. Check `cache_iterator_result` and `cache_coroutine_result` usage for keys that omit an argument affecting the result.
- Resources must be cleaned up (clients, files, tasks). Prefer context managers, and cancel and await spawned tasks.
- Rate limiting is centralised under `port_ocean/rate_limiting/`. Do not add ad-hoc per-call retries or sleeps that bypass it.

## Settings and configuration

- New settings need a default, validation, and a name that does not collide with existing settings or env vars.
- Anything user-facing needs documentation. Flag new settings or behaviour with no doc update where docs are expected.
- Secrets in settings must be typed and handled as sensitive.

## Webhook and live-event handling

- Keep the `AbstractWebhookProcessor` contract (`authenticate`, `validate_payload`, `handle_event`, `should_process_event`, `get_matching_kinds`) and retry semantics (`RetryableError`, backoff) intact.
- Redis live events match webhook paths exactly. Dynamic registration paths cause events to be acknowledged and dropped.
- A processor failure must not silently drop an event that should be retried, and must not retry forever.

## Errors and logging

- Use the existing custom exceptions in `port_ocean/exceptions/` instead of generic `Exception` where a specific one exists. New error cases should get a specific exception with an actionable message.
- Log with `loguru` at the right level and with enough context to debug. Never log secrets or payloads that may contain personal data.
