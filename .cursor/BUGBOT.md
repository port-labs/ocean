# Bugbot review guidance for Ocean

Ocean is a Python 3.12 framework (`port_ocean/`) plus ~50 integrations (`integrations/*`) that sync third-party data into Port's catalog. A bug in core affects every integration, and a bug in an integration can create or delete real customer catalog entities.

Area-specific rules live next to the code:

- `port_ocean/.cursor/BUGBOT.md` for framework changes
- `integrations/.cursor/BUGBOT.md` for integration changes

## How to review

- Prioritise correctness, data safety, security, and backward compatibility. Report real bugs and risks first.
- Always flag code cleanliness and typing issues too (see "Typed models" and "Code cleanliness" below). Present them as suggestions, not blockers, and leave it to the developer to decide whether to act. Do not stay silent just because an issue is minor, and do not insist or re-raise it once the developer has answered.
- Only comment on lines the PR adds or changes. Do not ask for refactors of untouched legacy code, but do apply the rules below to everything the PR touches, in every integration.
- Explain the concrete failure (what breaks, when, for whom) instead of stating a preference.
- Do not repeat what CI already enforces. These are checked automatically, so skip them:
  - `black`, `ruff`, `mypy` (core), `yamllint`, trailing whitespace and end-of-file fixes
  - PR title format (`[Core]`, `[Integration]`, `[Docs]`, `[CI]`, `[Infra]`, ...)
  - release-intent file presence and YAML format, and the integration `port_ocean` pin
- Do not flag these, because they are established conventions here:
  - f-strings in `logger.*` calls
  - `from loguru import logger` (this is the logger, not stdlib `logging`)
  - `.port/spec.json` (not `spec.yaml`) and camelCase configuration names in it

## Typed models: Pydantic over raw dicts (primary rule, always flag)

Structured data must be modelled with Pydantic (v2) `BaseModel`s, not passed around as raw `dict`s. This is one of the most important rules in this repo. Flag it every time it shows up in code the PR adds or changes:

- Function parameters or return values typed as `dict`, `dict[str, Any]`, `Dict`, `Mapping[str, Any]`, or left untyped when they carry a known shape (API request options and params, parsed API responses, config, selectors, intermediate results, kwargs bundles).
- Code that reads structured data with string keys (`data["id"]`, `data.get("owner", {}).get("name")`) when a model would give validation, defaults, and static typing.
- Hand-built dicts passed between functions or layers (client, exporter, helpers, webhook processors) instead of a model that documents and validates the contract.
- `TypedDict`, `NamedTuple`, or plain dataclasses introduced for data that is validated, parsed, or serialised. Prefer a Pydantic model so the shape is validated at the boundary.
- `Any` standing in for a structure that is actually known.

Recommend concretely: name the model, list its fields, and say where to parse (parse once at the boundary, for example `Model.model_validate(response)`, and pass the model onward).

Narrow exceptions (do not flag these):

- Raw items yielded from `@ocean.on_resync` and `@ocean.on_incremental_resync` handlers and webhook results are `RAW_ITEM` dicts by framework contract, because JQ mappings run on them. Models are still welcome for everything that happens before the item is yielded.
- Genuinely free-form third-party payloads that are passed through untouched, with no code reading specific keys.
- Test fixtures and mock payloads.

## Reuse in core: standalone code written inside an integration

When a PR adds a new util, helper, or abstraction inside an integration and it is standalone, meaning it has no dependency on that integration's API, models, or config, always flag it and recommend moving it to core (`port_ocean/utils/` or `port_ocean/helpers/`, or the matching core package) so every integration can reuse it. Typical examples:

- Generic retry, backoff, or rate-limit helpers; pagination or batching helpers; async-iterator, queue, or concurrency utilities.
- Generic caching wrappers, JSON/YAML/JQ or string and date helpers, and generic base classes or abstractions that would suit any integration.

Before recommending, check whether core already has an equivalent, and if it does, recommend reusing it instead of adding a second version (for example `port_ocean/utils/async_iterators.py`, `queue_utils.py`, `cache.py`, `port_ocean/rate_limiting/`, `port_ocean/helpers/retry.py`). If it is specific to one third-party system, leave it in the integration. As with other cleanliness points, this is a recommendation, and the developer decides.

## Code cleanliness (always flag; the developer decides)

- Dead code, commented-out code, leftover debug code (`print(...)`, `breakpoint()`, `pdb`, stray `TODO`/`FIXME` without context) in non-test code.
- Duplicated logic that should reuse an existing helper in `port_ocean/utils/` or the integration's own `helpers/`.
- Functions doing several unrelated things, or deeply nested branches where guard clauses and early returns would be clearer.
- Missing or misleading type hints on new or changed function signatures (and see "Typed models" above for structured data).
- Overly broad error handling: bare `except:`, `except Exception: pass`, or catching an error only to log and continue when the caller needs to know it failed. Prefer specific, custom exceptions with actionable messages.
- Raising builtin exceptions (`Exception`, `ValueError`, `RuntimeError`, `KeyError`, `TypeError`, and similar) in non-test code. Prefer a custom exception that names the failure and carries an actionable message. Reuse an existing one first (`port_ocean/exceptions/` for core, the integration's `helpers/exceptions.py` for integrations) and only add a new one when none fits. Custom exceptions let callers handle specific failures and keep resync error handling precise. Builtins that signal a genuine programming error (for example `NotImplementedError` in an abstract method) are fine.
- Comments that restate the code. Keep comments for non-obvious intent and complex logic only.
- Over-engineering: new abstractions, flags, or config nobody uses yet.
- Pointless wrapper functions: tiny functions that do close to nothing or literally nothing, such as one that only forwards its arguments to another function, renames a call, or wraps a single expression with no added logic, naming value, or reuse. Recommend inlining them. A small function is fine when it has a clear name for non-obvious logic, is reused, or is a deliberate seam (for example a test hook or an override point).

## Security (always flag)

- Logging, printing, or putting in exception messages any token, secret, password, API key, `Authorization` header, or personal data.
- Credentials, `.env` files, or tokens committed to the repo, including test fixtures that contain real-looking secrets.
- Secret-bearing configuration without `"sensitive": true` in `.port/spec.json`.
- Disabling TLS verification, or building URLs from untrusted input without validation.
- Webhook handlers that skip signature or auth verification.

## Release hygiene

CI checks that a release intent exists. Check that it is correct:

- Every PR that changes `port_ocean/` needs `.ocean-release/core/<name>.yaml`. Every PR that changes an integration needs `integrations/<name>/.ocean-release/<name>.yaml`.
- `bump` must match the real change:
  - `patch` for fixes and small improvements
  - `minor` for new features or new resource kinds
  - `major` for breaking changes
- Breaking behaviour must use `changelog-type: breaking` and `bump: major`. That includes removed or renamed config, kinds, blueprint properties, or public APIs.
- The `changelog` text must be user-facing and accurate for what this PR actually does.
- When a PR touches both core and an integration, the integration intent should describe only the integration's own change. Do not copy the core changelog into it.
- Feature PRs should not manually bump `pyproject.toml` or edit `CHANGELOG.md` unless the PR explicitly says so. Never edit an integration's version in a core-only change.
