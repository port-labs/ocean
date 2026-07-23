# Changelog - Ocean - cursor-cloud-agents

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0 (2026-07-19)

### Features

- Added resync support for the `agent` and `run` kinds via the Cursor Cloud Agents v1 API. Run resync enriches each run with per-run token usage from `GET /v1/agents/{id}/usage`.
- Added live-events (webhook) support that completes `create_agent`/`trigger_agent` Port workflow runs when `reportCompletion` is enabled on v0-created agents, and best-effort upserts `cursor_agent` / `cursor_run` catalog entities on terminal webhooks. Optionally configure `webhookSigningSecret` to sign outgoing callbacks and verify incoming webhooks; when unset, signature verification is skipped.
- Added two integration actions, `create_agent` and `trigger_agent`, invokable from Port workflows. `create_agent` takes an explicit `apiVersion` (`v0` or `v1`); `reportCompletion` only applies on v0 create (webhook tracking). `trigger_agent` always uses the v1 follow-up API; `reportCompletion` on trigger waits for the agent-level webhook when the agent was v0-created with tracking.
- `create_agent` and `trigger_agent` best-effort upsert `cursor_agent` / `cursor_run` catalog entities immediately after the Cursor API call.
