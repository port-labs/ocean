# Changelog - Ocean - Cursor

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.2 (2026-06-25)


### Improvements

- All Pydantic imports modified to v1 in order to allow for gradual migration to v2


## 0.1.1 (2026-06-22)


### Improvements

- Bumped ocean version to ^0.43.19


## 0.1.0 (2026-06-08)

### Features

- Added a new Cursor integration that exports team model usage, per-user model usage, daily usage data, and filtered usage events.
- Added configurable relative start/end date selectors with strict 30-day window validation for both the Analytics and Admin APIs.
