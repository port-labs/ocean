# Changelog - Ocean - claude

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.0 (2026-05-28)


### Breaking Changes

- Migrated from Anthropic Admin API to the new Enterprise Analytics API (`/v1/organizations/analytics/`). The `anthropicVersion` configuration option has been removed; the API key must now be an analytics API key with `read:analytics` scope, created at `claude.ai/analytics/api-keys`.
- Replaced `claude-code-analytics` kind (backed by the deprecated `/v1/organizations/usage_report/claude_code` endpoint) with `claude-user-activity` (backed by `GET /v1/organizations/analytics/users`). The selector fields (`startingDate`/`timeFrame`) are unchanged.
- Updated `claude-usage-record` groupBy options: removed `api_key_id`, `workspace_id`, `account_id`, `service_account_id`, `service_tier`; added `product`.


### Improvements

- Added `list_amount` field to `claude-cost-record` blueprint (pre-discount cost in fractional cents).
- Added groupBy support to `claude-cost-record` (`cost_type`, `token_type`, `product`, `model`, `context_window`, `speed`, `inference_geo`).
- Added four new kinds backed by new Enterprise Analytics API endpoints:
  - `claude-user-activity` — per-user daily engagement including Claude Code metrics (lines added/removed, sessions, commits, PRs, tool acceptance). Selector fields (`startingDate`/`timeFrame`) are the same as the retired `claude-code-analytics` kind.
  - `claude-activity-summary` — organisation-level DAU/WAU/MAU and seat allocation.
  - `claude-user-usage-report` — per-user token consumption ranking with model/product breakdown.
  - `claude-user-cost-report` — per-user cost ranking (discounted and list price).


## 0.1.19 (2026-05-28)


### Improvements

- Bumped ocean version to ^0.43.2


## 0.1.18 (2026-05-26)


### Improvements

- Bumped ocean version to ^0.43.1


## 0.1.17 (2026-05-25)


### Improvements

- Bumped ocean version to ^0.43.0


## 0.1.16 (2026-05-25)


### Improvements

- Bumped ocean version to ^0.42.11


## 0.1.15 (2026-05-25)


### Improvements

- Bumped ocean version to ^0.42.10


## 0.1.14 (2026-05-24)


### Improvements

- Bumped ocean version to ^0.42.9


## 0.1.13 (2026-05-21)


### Improvements

- Bumped ocean version to ^0.42.8


## 0.1.12 (2026-05-21)


### Improvements

- Bumped ocean version to ^0.42.7


## 0.1.11 (2026-05-19)


### Improvements

- Bumped ocean version to ^0.42.6


## 0.1.10 (2026-05-19)


### Improvements

- Bumped ocean version to ^0.42.5


## 0.1.9 (2026-05-17)


### Improvements

- Bumped ocean version to ^0.42.4


## 0.1.8 (2026-05-17)


### Improvements

- Bumped ocean version to ^0.42.3


## 0.1.7 (2026-05-17)


### Improvements

- Bumped ocean version to ^0.42.2


## 0.1.6 (2026-05-14)


### Improvements

- Bumped ocean version to ^0.42.1


## 0.1.5 (2026-05-14)


### Improvements

- Bumped ocean version to ^0.42.0


## 0.1.4 (2026-05-13)


### Improvements

- Bumped ocean version to ^0.41.9


## 0.1.3 (2026-05-12)


### Improvements

- Bumped ocean version to ^0.41.8


## 0.1.2 (2026-05-10)


### Improvements

- Added `timeFrame` selector field to `claude-code-analytics` kind — accepts a number of days to look back and calls the API once per day for each day in the window. `timeFrame` and `startingDate` are mutually exclusive (one is required); `startingDate` iterates from the given date to today


## 0.1.1 (2026-05-07)


### Improvements

- Bumped ocean version to ^0.41.7


## 0.1.0 (2025-04-02)

### Features

- Implemented claude ai ocean integration (0.1.0) with `claude-usage-record`, `claude-cost-record` and `claude-code-analytics` kinds.
