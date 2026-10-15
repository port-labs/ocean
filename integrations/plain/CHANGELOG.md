# Changelog - Ocean - plain

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.3-beta (2026-10-13)


### Improvements

- Bumped ocean version to ^0.54.0


## 0.1.2-beta (2026-10-12)


### Improvements

- Bumped ocean version to ^0.53.9


## 0.1.1-beta (2026-10-12)


### Improvements

- Bumped ocean version to ^0.53.8


## 0.1.0-beta (2026-10-06)


### Features

- Added Plain Ocean integration with resync for companies, tenants, users, machine users, customers, threads, thread messages, discussions, and discussion messages
- Added selector flags for page size, excluding done threads, optional thread statuses, deleted machine users, and AI/agent-session discussions
- Added live events gated by the Ocean event listener (`should_process_webhooks`), with webhook registration that continues startup when the API key cannot create the target
- Opted GraphQL POSTs into Ocean RetryTransport so Plain 429s wait instead of failing the kind

