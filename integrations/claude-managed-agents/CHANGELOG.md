# Changelog - Ocean - claude-managed-agents

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.12 (2026-07-19)


### Improvements

- Bumped ocean version to ^0.45.4


## 0.1.11 (2026-07-16)


### Improvements

- Bumped ocean version to ^0.45.3


## 0.1.10 (2026-07-16)


### Improvements

- Bumped ocean version to ^0.45.2


## 0.1.9 (2026-07-16)


### Improvements

- Bumped ocean version to ^0.45.1


## 0.1.8 (2026-07-15)


### Improvements

- Bumped ocean version to ^0.45.0


## 0.1.7 (2026-07-15)


### Improvements

- Bumped ocean version to ^0.44.14


## 0.1.6 (2026-07-14)


### Improvements

- Bumped ocean version to ^0.44.13


## 0.1.5 (2026-07-14)


### Improvements

- Bumped ocean version to ^0.44.12


## 0.1.4 (2026-07-13)


### Improvements

- Bumped ocean version to ^0.44.11


## 0.1.3 (2026-07-12)


### Improvements

- Bumped ocean version to ^0.44.10


## 0.1.2 (2026-07-12)


### Improvements

- Bumped ocean version to ^0.44.9


## 0.1.1 (2026-07-12)


### Improvements

- Bumped ocean version to ^0.44.8


## 0.1.0 (2026-06-28)

### Features

- Added resync support for the `agent`, `environment`, `session`, `vault`, `memory-store` and `skill` kinds via the official Anthropic Python SDK (Managed Agents beta).
- Added live-events (webhooks) support that keeps `session` and `vault` entities up to date and reports `trigger_agent` node-run status back to Port.
- Added two integration actions, `create_agent` and `trigger_agent`, invokable from Port workflows.
