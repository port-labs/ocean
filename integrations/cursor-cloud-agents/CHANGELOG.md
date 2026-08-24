# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.22 (2026-08-24)


### Improvements

- Bumped ocean version to ^0.49.0


## 0.1.21 (2026-08-24)


### Improvements

- Bumped ocean version to ^0.48.13


## 0.1.20 (2026-08-20)


### Bug Fixes

- Use a static /integration/webhook URL and the configured webhookSigningSecret so SaaS Redis live-events can complete reportCompletion runs.


## 0.1.19 (2026-08-18)


### Improvements

- Bumped ocean version to ^0.48.12


## 0.1.18 (2026-08-17)


### Improvements

- Bumped ocean version to ^0.48.10


## 0.1.17 (2026-08-17)


### Improvements

- Bumped ocean version to ^0.48.9


## 0.1.16 (2026-08-16)


### Improvements

- Bumped ocean version to ^0.48.8


## 0.1.15 (2026-08-13)


### Improvements

- Bumped ocean version to ^0.48.7


## 0.1.14 (2026-08-13)


### Improvements

- Bumped ocean version to ^0.48.6


## 0.1.13 (2026-08-13)


### Improvements

- Bumped ocean version to ^0.48.5


## 0.1.12 (2026-08-12)


### Improvements

- Bumped ocean version to ^0.48.4


## 0.1.11 (2026-08-11)


### Improvements

- Bumped ocean version to ^0.48.3


## 0.1.10 (2026-08-10)


### Improvements

- Bumped ocean version to ^0.48.2


## 0.1.9 (2026-08-10)


### Improvements

- Bumped ocean version to ^0.48.1


## 0.1.8 (2026-08-09)


### Improvements

- Bumped ocean version to ^0.47.10


## 0.1.7 (2026-08-09)


### Improvements

- Bumped ocean version to ^0.47.9


## 0.1.6 (2026-08-09)


### Improvements

- Bumped ocean version to ^0.47.8


## 0.1.5 (2026-08-05)


### Improvements

- Bumped ocean version to ^0.47.7


## 0.1.4 (2026-08-04)


### Improvements

- Bumped ocean version to ^0.47.6


## 0.1.3 (2026-08-04)


### Improvements

- Bump poetry to 2.X with range


## 0.1.2 (2026-08-03)


### Improvements

- Bumped ocean version to ^0.47.4


## 0.1.1 (2026-08-03)


### Improvements

- Bumped ocean version to ^0.47.3


## 0.1.0 (2026-07-19)


### Features

- Added resync support for the `agent` and `run` kinds via the Cursor Cloud Agents v1 API. Run resync enriches each run with per-run token usage from `GET /v1/agents/{id}/usage`.
- Added live-events (webhook) support that completes `create_agent`/`trigger_agent` Port workflow runs when `reportCompletion` is enabled on v0-created agents, and best-effort upserts `cursor_agent` / `cursor_run` catalog entities on terminal webhooks. Optionally configure `webhookSigningSecret` to sign outgoing callbacks and verify incoming webhooks; when unset, signature verification is skipped.
- Added two integration actions, `create_agent` and `trigger_agent`, invokable from Port workflows. `create_agent` takes an explicit `apiVersion` (`v0` or `v1`); `reportCompletion` only applies on v0 create (webhook tracking). `trigger_agent` always uses the v1 follow-up API; `reportCompletion` on trigger waits for the agent-level webhook when the agent was v0-created with tracking.
- `create_agent` and `trigger_agent` best-effort upsert `cursor_agent` / `cursor_run` catalog entities immediately after the Cursor API call.
