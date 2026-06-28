# Changelog - Ocean - claude-managed-agents

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0 (2026-06-28)

### Features

- Added resync support for the `agent`, `environment`, `session`, `vault` and `memory-store` kinds via the official Anthropic Python SDK (Managed Agents beta).
- Added live-events (webhooks) support that keeps `session` and `vault` entities up to date and reports `trigger_agent` node-run status back to Port.
- Added two integration actions, `create_agent` and `trigger_agent`, invokable from Port workflows.
