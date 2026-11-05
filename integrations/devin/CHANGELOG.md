# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0-beta (2026-10-20)


### Features

- Added resync support for the `session`, `playbook`, `knowledge-note` and `secret` kinds via the Devin v3 API.
- Added four integration actions: `create_session`, `send_message`, `terminate_session` and `archive_session`, invokable from Port workflows and self-service actions. Each best-effort upserts the `devin_session` entity.
- Added poll-based run tracking for `create_session` and `send_message` with `reportCompletion`. Sessions are tagged with the Port run's external ID; the tracker posts session messages to the run log, records when the turn started and ended, completes the run with the session output, and recovers in-flight runs after a restart.
