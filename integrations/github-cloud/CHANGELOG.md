# Changelog - Ocean - github-cloud

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->
# CHANGELOG.md

## [0.1.0-beta] - 2024-05-20

### Added
- Initial release of the GitHub Cloud integration for Port Ocean
- Full support for resyncing GitHub resources:
  - Repositories (with optional language info)
  - Pull Requests (enriched with repository info)
  - Issues (open and closed, enriched with repository info)
  - Teams with members (with optional bot member inclusion)
  - Members
  - Workflows (with content mapped to Port's blueprint)
- Real-time webhook event processing for:
  - Repository, Pull Request, Issue, and Workflow events
- Automatic webhook creation for organizations and repositories (unless in ONCE mode)
- Pagination handling for all list-based API calls to GitHub
- Rate limit backoff and error handling for 429 responses
- Configurable integration via `.port/spec.yaml` and environment variables
- Developer tooling:
  - Makefile for install, test, lint, format, type-check, security, and Docker
  - Poetry for dependency management
  - Towncrier for changelog automation
  - Full test suite and CI-ready scripts

### Removed
- All unused code and placeholder handlers
- Redundant or unused imports

### Notes
- Built on Port Ocean's async HTTP client and event-driven framework
- Ready for CI test pass and documentation submission
- See README for setup, development, and contributing guidelines
