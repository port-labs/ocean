# Changelog - Ocean - plain

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.3.4-beta (2026-11-19)


### Improvements

- Bumped ocean version to ^0.61.8


## 0.3.3-beta (2026-11-19)


### Improvements

- Bumped ocean version to ^0.61.7


## 0.3.2-beta (2026-11-17)


### Improvements

- Bumped ocean version to ^0.61.6


## 0.3.1-beta (2026-11-17)


### Improvements

- Bumped ocean version to ^0.61.5


## 0.3.0-beta (2026-11-17)


### Improvements

- |
    Improved error handling for test connection and webhook setup:
- Test connection now fails immediately on HTTP 401 (Unauthorized) with exactly one request instead of retrying ~10 times
- Test connection detects SSL/TLS certificate errors and provides clear messaging about secure connection issues
- Blocked IP addresses (from network security policy) are treated as test connection failures with clear messaging, not internal errors
- Webhook registration now logs a warning instead of crashing when Plain API cannot be reached
- Note: Resync and webhook calls continue to use normal retry behavior including for SSL errors


## 0.2.16-beta (2026-11-15)


### Improvements

- Bumped ocean version to ^0.61.4


## 0.2.15-beta (2026-11-15)


### Improvements

- Bumped ocean version to ^0.61.3


## 0.2.14-beta (2026-11-15)


### Improvements

- Bumped ocean version to ^0.61.2


## 0.2.13-beta (2026-11-12)


### Improvements

- Bumped ocean version to ^0.61.1


## 0.2.12-beta (2026-11-12)


### Improvements

- Bumped ocean version to ^0.61.0


## 0.2.11-beta (2026-11-12)


### Improvements

- Bumped ocean version to ^0.60.0


## 0.2.10-beta (2026-11-11)


### Improvements

- Bumped ocean version to ^0.59.0


## 0.2.9-beta (2026-11-11)


### Improvements

- Bumped ocean version to ^0.58.4


## 0.2.8-beta (2026-11-09)


### Improvements

- Bumped ocean version to ^0.58.3


## 0.2.7-beta (2026-11-08)


### Improvements

- Bumped ocean version to ^0.58.2


## 0.2.6-beta (2026-11-05)


### Improvements

- Bumped ocean version to ^0.58.1


## 0.2.5-beta (2026-11-04)


### Improvements

- Bumped ocean version to ^0.58.0


## 0.2.4-beta (2026-11-03)


### Improvements

- Bumped ocean version to ^0.57.0


## 0.2.3-beta (2026-11-02)


### Improvements

- Bumped ocean version to ^0.56.5


## 0.2.2-beta (2026-11-01)


### Improvements

- Bumped ocean version to ^0.56.4


## 0.2.1-beta (2026-10-29)


### Improvements

- Bumped ocean version to ^0.56.3


## 0.2.0-beta (2026-10-26)


### Features

- Add a connection probe that verifies Plain API authentication and per-kind permissions via myPermissions


## 0.1.15-beta (2026-10-26)


### Improvements

- Bumped ocean version to ^0.56.2


## 0.1.14-beta (2026-10-25)


### Improvements

- Bumped ocean version to ^0.56.1


## 0.1.13-beta (2026-10-25)


### Improvements

- Bumped ocean version to ^0.56.0


## 0.1.12-beta (2026-10-25)


### Improvements

- Bumped ocean version to ^0.55.6


## 0.1.11-beta (2026-10-22)


### Improvements

- Bumped ocean version to ^0.55.5


## 0.1.10-beta (2026-10-22)


### Improvements

- Bumped ocean version to ^0.55.4


## 0.1.9-beta (2026-10-21)


### Improvements

- Bumped ocean version to ^0.55.3


## 0.1.8-beta (2026-10-21)


### Improvements

- Bumped ocean version to ^0.55.2


## 0.1.7-beta (2026-10-20)


### Improvements

- Bumped ocean version to ^0.55.1


## 0.1.6-beta (2026-10-20)


### Improvements

- Enabled formMappingEnabled flag
- Converted `.port/spec.yaml` to `.port/spec.json` and added `title` and `docs`


## 0.1.5-beta (2026-10-20)


### Improvements

- Bumped ocean version to ^0.55.0


## 0.1.4-beta (2026-10-18)


### Improvements

- Bumped ocean version to ^0.54.1


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

