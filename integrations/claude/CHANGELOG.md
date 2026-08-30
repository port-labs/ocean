# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.57 (2026-08-30)


### Improvements

- Bumped ocean version to ^0.50.2


## 0.2.56 (2026-08-27)


### Improvements

- Bumped ocean version to ^0.50.2


## 0.2.55 (2026-08-26)


### Improvements

- Converted specs from yaml to json


## 0.2.54 (2026-08-26)


### Improvements

- Bumped ocean version to ^0.50.1


## 0.2.53 (2026-08-24)


### Improvements

- Bumped ocean version to ^0.49.1


## 0.2.52 (2026-08-24)


### Improvements

- Bumped ocean version to ^0.49.0


## 0.2.51 (2026-08-24)


### Improvements

- Bumped ocean version to ^0.48.13


## 0.2.50 (2026-08-18)


### Improvements

- Bumped ocean version to ^0.48.12


## 0.2.49 (2026-08-17)


### Improvements

- Bumped ocean version to ^0.48.10


## 0.2.48 (2026-08-17)


### Bug Fixes

- Use a 2-day lag for skill-usage date windows so the latest day matches when Anthropic actually serves data (docs cite ~1 day but availability often lags further).
- Restore startup API verification to a single `/analytics/users` probe; one `read:analytics` check is sufficient and avoids noisy 400s from the skills endpoint.


## 0.2.47 (2026-08-17)


### Improvements

- Bumped ocean version to ^0.48.9


## 0.2.46 (2026-08-16)


### Improvements

- Split deprecated Claude kind aliases onto dedicated ResourceConfig classes.


## 0.2.45 (2026-08-16)


### Improvements

- Bumped ocean version to ^0.48.8


## 0.2.44 (2026-08-13)


### Improvements

- Added `claude-ai-skill-usage` kind for org-level Claude Skills Analytics, syncing per-skill usage into the `claude_ai_skill_usage` blueprint.


## 0.2.43 (2026-08-13)


### Improvements

- Bumped ocean version to ^0.48.7
- Added `claude-ai-skill-usage` kind for org-level Claude Skills Analytics, syncing per-skill usage into the `claude_ai_skill_usage` blueprint.


## 0.2.42 (2026-08-13)


### Improvements

- Bumped ocean version to ^0.48.6


## 0.2.41 (2026-08-13)


### Improvements

- Bumped ocean version to ^0.48.5


## 0.2.40 (2026-08-12)


### Improvements

- Bumped ocean version to ^0.48.4


## 0.2.39 (2026-08-11)


### Improvements

- Bumped ocean version to ^0.48.3


## 0.2.38 (2026-08-10)


### Improvements

- Bumped ocean version to ^0.48.2


## 0.2.37 (2026-08-10)


### Improvements

- Bumped ocean version to ^0.48.1


## 0.2.36 (2026-08-09)


### Improvements

- Bumped ocean version to ^0.47.10


## 0.2.35 (2026-08-09)


### Improvements

- Bumped ocean version to ^0.47.9


## 0.2.34 (2026-08-09)


### Improvements

- Bumped ocean version to ^0.47.8


## 0.2.33 (2026-08-05)


### Improvements

- Bumped ocean version to ^0.47.7


## 0.2.32 (2026-08-04)


### Improvements

- Bumped ocean version to ^0.47.6


## 0.2.31 (2026-08-04)


### Improvements

- Bump poetry to 2.X with range


## 0.2.30 (2026-08-03)


### Improvements

- Bumped ocean version to ^0.47.4


## 0.2.29 (2026-08-03)


### Improvements

- Bumped ocean version to ^0.47.3


## 0.2.28 (2026-07-30)


### Improvements

- Bumped ocean version to ^0.47.2


## 0.2.27 (2026-07-29)


### Improvements

- Bumped ocean version to ^0.47.1


## 0.2.26 (2026-07-29)


### Improvements

- Bumped ocean version to ^0.47.0


## 0.2.25 (2026-07-29)


### Improvements

- Bumped ocean version to ^0.46.6


## 0.2.24 (2026-07-28)


### Improvements

- Bumped ocean version to ^0.46.5


## 0.2.23 (2026-07-27)


### Improvements

- Bumped ocean version to ^0.46.4


## 0.2.22 (2026-07-27)


### Improvements

- Bumped ocean version to ^0.46.3


## 0.2.21 (2026-07-26)


### Improvements

- Bumped ocean version to ^0.46.2


## 0.2.20 (2026-07-23)


### Improvements

- Bumped ocean version to ^0.46.1


## 0.2.19 (2026-07-23)


### Improvements

- Bumped ocean version to ^0.46.0


## 0.2.18 (2026-07-22)


### Improvements

- Bumped ocean version to ^0.45.10


## 0.2.17 (2026-07-22)


### Improvements

- Bumped ocean version to ^0.45.8


## 0.2.16 (2026-07-21)


### Improvements

- Bumped ocean version to ^0.45.7


## 0.2.15 (2026-07-21)


### Improvements

- Bumped ocean version to ^0.45.6


## 0.2.14 (2026-07-21)


### Improvements

- Upgraded integration dependencies (#1)


## 0.2.13 (2026-07-20)


### Improvements

- Bumped ocean version to ^0.45.5


## 0.2.12 (2026-07-19)


### Improvements

- Bumped ocean version to ^0.45.4


## 0.2.11 (2026-07-16)


### Improvements

- Bumped ocean version to ^0.45.3


## 0.2.10 (2026-07-16)


### Improvements

- Bumped ocean version to ^0.45.2


## 0.2.9 (2026-07-16)


### Improvements

- Bumped ocean version to ^0.45.1


## 0.2.8 (2026-07-15)


### Improvements

- Bumped ocean version to ^0.45.0


## 0.2.7 (2026-07-15)


### Improvements

- Bumped ocean version to ^0.44.14


## 0.2.6 (2026-07-14)


### Improvements

- Bumped ocean version to ^0.44.13


## 0.2.5 (2026-07-14)


### Improvements

- Bumped ocean version to ^0.44.12


## 0.2.4 (2026-07-13)


### Improvements

- Bumped ocean version to ^0.44.11


## 0.2.3 (2026-07-12)


### Improvements

- Bumped ocean version to ^0.44.10


## 0.2.2 (2026-07-12)


### Improvements

- Bumped ocean version to ^0.44.9


## 0.2.1 (2026-07-12)


### Improvements

- Bumped ocean version to ^0.44.8


## 0.2.0 (2026-07-09)


### Breaking Changes

- Renamed the Claude Platform kinds to the `claude-platform-*` pattern (old names kept as deprecated aliases).
- Default resources and blueprints now target Claude AI (Enterprise) instead of Claude Platform.


### Features

- Added an `isClaudeEnterprise` toggle (default enabled) to switch between Claude AI (Enterprise) and Claude Platform.
- Added Claude AI (Enterprise) kinds for the per-user analytics endpoints: `claude-ai-user-activity`, `claude-ai-user-usage`, and `claude-ai-user-cost`.


### Improvements

- Skip and log resyncs for kinds that don't match the configured deployment instead of failing with 401/403.
- Validate and clamp analytics date ranges to Anthropic's limits.


## 0.1.43 (2026-07-08)


### Improvements

- Bumped ocean version to ^0.44.7


## 0.1.42 (2026-07-08)


### Improvements

- Bumped ocean version to ^0.44.6


## 0.1.41 (2026-07-02)


### Improvements

- Bumped ocean version to ^0.44.5


## 0.1.40 (2026-06-30)


### Improvements

- Bumped ocean version to ^0.44.4


## 0.1.39 (2026-06-28)


### Improvements

- Bumped ocean version to ^0.44.3


## 0.1.38 (2026-06-28)


### Improvements

- Bumped ocean version to ^0.44.2


## 0.1.37 (2026-06-25)


### Improvements

- Bumped ocean version to ^0.44.1


## 0.1.36 (2026-06-25)


### Improvements

- All Pydantic imports modified to v1 in order to allow for gradual migration to v2


## 0.1.35 (2026-06-22)


### Improvements

- Bumped ocean version to ^0.43.19


## 0.1.34 (2026-06-15)


### Improvements

- Bumped ocean version to ^0.43.18


## 0.1.33 (2026-06-11)


### Improvements

- Bumped ocean version to ^0.43.17


## 0.1.32 (2026-06-09)


### Improvements

- Bumped ocean version to ^0.43.16


## 0.1.31 (2026-06-07)


### Improvements

- Bumped ocean version to ^0.43.15


## 0.1.30 (2026-06-03)


### Improvements

- Bumped ocean version to ^0.43.14


## 0.1.29 (2026-06-03)


### Improvements

- Bumped ocean version to ^0.43.13


## 0.1.28 (2026-06-02)


### Improvements

- Bumped ocean version to ^0.43.12


## 0.1.27 (2026-06-02)


### Improvements

- Bumped ocean version to ^0.43.11


## 0.1.26 (2026-06-01)


### Improvements

- Bumped ocean version to ^0.43.10


## 0.1.25 (2026-05-31)


### Improvements

- Bumped ocean version to ^0.43.9


## 0.1.24 (2026-05-31)


### Improvements

- Bumped ocean version to ^0.43.8


## 0.1.23 (2026-05-31)


### Improvements

- Bumped ocean version to ^0.43.7


## 0.1.22 (2026-05-31)


### Improvements

- Bumped ocean version to ^0.43.6


## 0.1.21 (2026-05-29)


### Improvements

- Bumped ocean version to ^0.43.4


## 0.1.20 (2026-05-28)


### Improvements

- Bumped ocean version to ^0.43.3


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
