# Changelog - Ocean - GitHub Integration

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [0.2.0] - 2025-05-24

### Changed
- Renamed integration identifier from `azeez_github` to `github`
- Updated environment variables to use Ocean integration config pattern:
  - `OCEAN__GITHUB_TOKEN` -> `OCEAN__INTEGRATION__CONFIG__GITHUB_TOKEN`
  - `OCEAN__GITHUB_ORG` -> `OCEAN__INTEGRATION__CONFIG__GITHUB_ORG`
  - `OCEAN__GITHUB_REPO` -> `OCEAN__INTEGRATION__CONFIG__GITHUB_REPO`
  - `OCEAN__GITHUB_BASE_URL` -> `OCEAN__INTEGRATION__CONFIG__GITHUB_BASE_URL`
- Improved blueprint definitions with better schemas and relations:
  - Added rich data types and formats (markdown, url, date-time)
  - Added enum colors for status fields
  - Added proper relations between entities
  - Renamed blueprints to follow consistent naming:
    - `repositories` -> `githubRepository`
    - `issues` -> `githubIssue`
    - `pull_requests` -> `githubPullRequest`
    - `workflows` -> `githubWorkflow`
    - `teams` -> `githubTeam`

### Added
- New fields and properties to entity schemas:
  - Repository: readme, defaultBranch, teams relation
  - Issue: creator, assignees, labels, timestamps
  - Pull Request: reviewers, merge status, lead time calculation
  - Workflow: path, status enums, timestamps
  - Team: permissions, notification settings

### Removed
- Removed `config.yaml` in favor of environment variables
- Removed `config_model.py` as it's no longer needed
- Removed `utils.py` and moved constants to `constants.py`
- Removed `github_client.py` and reorganized into `client/` module

### Fixed
- Improved logging format to match Ocean standards
- Better type hints and docstrings
- More consistent code organization
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

