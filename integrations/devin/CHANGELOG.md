# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.3 (2026-11-25)


### Improvements

- Bumped ocean version to ^0.63.0


## 0.2.2 (2026-11-24)


### Improvements

- Bumped ocean version to ^0.62.4


## 0.2.1 (2026-11-24)


### Improvements

- Bumped ocean version to ^0.62.3


## 0.2.0 (2026-11-23)


### Features

- Add enablePortMcp on create_session and send_message to inject the workflow user's Port JWT into Devin session_secrets under MCP_PORT_TOKEN.


## 0.1.0 (2026-10-20)


### Features

- Added resync support for the `session`, `playbook`, `knowledge-note` and `secret` kinds via the Devin v3 API.
- Added four integration actions: `create_session`, `send_message`, `terminate_session` and `archive_session`, invokable from Port workflows and self-service actions. Each best-effort upserts the `devin_session` entity.
- Added poll-based run tracking for `create_session` and `send_message` with `reportCompletion`. Sessions are tagged with the Port run's external ID; the tracker posts session messages to the run log, records when the turn started and ended, completes the run with the session output, and recovers in-flight runs after a restart.


### Improvements

- Parse Devin list payloads in best-effort mode so one bad session or message does not fail session tracking.
