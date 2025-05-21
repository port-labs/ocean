# Changelog - Ocean - azeez_github

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->
# CHANGELOG.md

## [0.1.0-beta] - 2025-05-20

### Added
- Initial GitHub Cloud integration using Port Ocean framework
- Repository, Issues, PRs, Teams, and Workflows resync support
- Webhook listener for GitHub `push`, `pull_request`, and `issues` events
- Pagination handling for all list-based API calls
- Rate limit backoff strategy for 429 responses
- Config model loading from environment
- Basic app config YAML file under `.port/`

### Removed
- All unused code and placeholder handlers
- Redundant FastAPI-specific imports

### Notes
- Built entirely with Ocean's custom async HTTP client
- Ready for CI test pass and final documentation submission

