# Bugbot review guidance for Ocean

Ocean is a Python 3.12 framework (`port_ocean/`) plus ~50 integrations (`integrations/*`) that sync third-party data into Port's catalog. A bug in core affects every integration, and a bug in an integration can create or delete real customer catalog entities.

Area-specific rules live next to the code:

- `port_ocean/.cursor/BUGBOT.md` for framework changes
- `integrations/.cursor/BUGBOT.md` for integration changes

## How to review

- Prioritise correctness, data safety, security, and backward compatibility. Report real bugs and risks first.
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

## Code cleanliness (flag when it hurts readability or correctness)

- Dead code, commented-out code, leftover debug code (`print(...)`, `breakpoint()`, `pdb`, stray `TODO`/`FIXME` without context) in non-test code.
- Duplicated logic that should reuse an existing helper in `port_ocean/utils/` or the integration's own `helpers/`.
- Functions doing several unrelated things, or deeply nested branches where guard clauses and early returns would be clearer.
- Missing or misleading type hints on new or changed function signatures. Prefer Pydantic models or `TypedDict` over raw `dict` for structured data.
- Overly broad error handling: bare `except:`, `except Exception: pass`, or catching an error only to log and continue when the caller needs to know it failed. Prefer specific, custom exceptions with actionable messages.
- Comments that restate the code. Keep comments for non-obvious intent and complex logic only.
- Over-engineering: new abstractions, flags, or config nobody uses yet.

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
