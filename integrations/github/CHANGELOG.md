# Changelog - Ocean - github

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 3.0.5-beta (2025-11-03)


### Features

- Added bot filtering option for GitHub user sync


## 3.0.4-beta (2025-11-02)


### Improvements

- Bumped ocean version to ^0.28.19


## 3.0.3-beta (2025-10-27)


### Improvements

- Bumped ocean version to ^0.28.18


## 3.0.2-beta (2025-10-26)


### Improvements

- Bumped ocean version to ^0.28.17


## 3.0.1-beta (2025-10-21)


### Improvements

- Bumped ocean version to ^0.28.16


## 3.0.0-beta (2025-10-20)


### Features

- Added multi-organization support for GitHub integration
- Updated all resync functions to iterate through multiple organizations
- Modified webhook processors to include organization context
- Updated exporters to support organization parameters
- Added `organization` as a new resource kind


## 2.0.3-beta (2025-10-20)


### Improvements

- Bumped ocean version to ^0.28.15


## 2.0.2-beta (2025-10-15)


### Bug Fixes

- Updated Closed Pull Request Tests with Mocked Datetime


## 2.0.1-beta (2025-10-15)


### Improvements

- Bumped ocean version to ^0.28.14


## 2.0.0-beta (2025-09-30)


### Improvements

- Bumped ocean version to ^0.28.12


## 1.5.9-beta (2025-09-28)


### Improvements

- Bumped ocean version to ^0.28.11


## 1.5.8-beta (2025-09-25)


### Improvements

- Bumped ocean version to ^0.28.9


## 1.5.7-beta (2025-09-25)


### Improvements

- Bumped ocean version to ^0.28.8


## 1.5.6-beta (2025-09-17)

### Improvements

- Fix token decoder from oauth-flow


## 1.5.5-beta (2025-09-17)


### Improvements

- Bumped ocean version to ^0.28.7


## 1.5.4-beta (2025-09-16)


### Improvements

- Bumped ocean version to ^0.28.5


## 1.5.3-beta (2025-09-10)


### Improvements

- Bumped ocean version to ^0.28.4


## 1.5.2-beta (2025-09-08)


### Improvements

- Added GitHub API rate limiting with concurrency control
- Implemented GitHubRateLimiter based on GitHub's rate limit headers
- Added separate rate limit tracking for Rest and GraphQL endpoints
- Added semaphore-based concurrency control (default: 10 concurrent requests)
- Integrated rate limiting into base client with configurable parameters
- Improved error handling to distinguish between rate limit and permission errors
- Added rate limit monitoring and comprehensive logging


## 1.5.1-beta (2025-09-08)


### Improvements

- Bumped ocean version to ^0.28.3


## 1.5.0-beta (2025-09-04)


### Features

- Added support for Secret Scanning Alerts with new kind `secret-scanning-alerts`
- New Secret Scanning Alert exporter and webhook processor for real-time alert monitoring
- Support for filtering Secret Scanning Alerts by state (open, resolved, all)
- Added `hide_secret` selector option to control whether sensitive secret content is exposed in alert data
- Comprehensive webhook event mapping for Secret Scanning Alerts: created, publicly_leaked, reopened, resolved, validated


## 1.4.2-beta (2025-08-28)


### Features

- Enhanced branch exporter functionality with improved branch data processing and export capabilities
- Improved branch webhook processor to handle branch-related events more efficiently


## 1.4.1-beta (2025-08-28)


### Improvements

- Bumped ocean version to ^0.28.2


## 1.4.0-beta (2025-08-27)


- Enhanced repository selector to support multiple relationship types simultaneously
- Changed `included_property` to `included_relationships` to allow specifying both "collaborators" and "teams" in a single configuration
- Improved repository enrichment logic to handle multiple relationships efficiently


## 1.3.6-beta (2025-08-27)


### Improvements

- Bumped ocean version to ^0.28.1


## 1.3.5-beta (2025-08-26)


### Improvements

- Bumped ocean version to ^0.28.0


## 1.3.4-beta (2025-08-25)


### Bug Fixes

- Improved test reliability by using fixture-based datetime mocking instead of inline patching
- Consolidated datetime mocking logic into reusable fixture


## 1.3.3-beta (2025-08-24)


### Improvements

- Bumped ocean version to ^0.27.10


## 1.3.2-beta (2025-08-20)


### Improvements

- Bumped ocean version to ^0.27.9


## 1.3.1-beta (2025-08-19)


### Improvements

- Include name in GraphQL response for User and Team Member Kind


## 1.3.0-beta (2025-08-18)


### Improvements

- Added maxResults and since config options to include closed PRs during export
- Added Batch limiting (max 100 closed PRs) to prevent performance issues
- Modified Webhook processor to update (not delete) closed PRs when maxResults flag is enabled


## 1.2.11-beta (2025-08-18)


### Improvements

- Bumped ocean version to ^0.27.8


## 1.2.10-beta (2025-08-17)


### Improvements

- Bumped ocean version to ^0.27.7


## 1.2.9-beta (2025-08-13)


### Improvements

- Bumped ocean version to ^0.27.6


## 1.2.8-beta (2025-08-13)


### Improvements

- Bumped ocean version to ^0.27.5


## 1.2.7-beta (2025-08-11)


### Improvements

- Bumped ocean version to ^0.27.3


## 1.2.6-beta (2025-08-11)


### Improvements

- Bumped ocean version to ^0.27.2


## 1.2.5-beta (2025-08-07)


### Improvements

- Bumped ocean version to ^0.27.1


## 1.2.4-beta (2025-08-06)


### Improvements

- Improved folder kind ingestion performance by using the GitHub Search API to efficiently retrieve repository information.


## 1.2.3-beta (2025-08-05)


### Improvements

- Bumped ocean version to ^0.27.0


## 1.2.2-beta (2025-08-04)


### Improvements

- Bumped ocean version to ^0.26.3


## 1.2.1-beta (2025-08-03)


### Improvements

- Bumped ocean version to ^0.26.2


## 1.2.0-beta (2025-07-28)


### Features

- Added File validation for pull requests with GitHub check run integration
- Enhanced pull request webhook processor to trigger validation on open/sync events


## 1.1.2-beta (2025-07-25)


### Improvements

- Added improvement for selecting collaborators and team relationships on repository kind


## 1.1.1-beta (2025-07-24)


### Improvements

- Properly handle empty repo errors when ingesting files
- Properly handle empty repo errors when ingesting folders


## 1.1.0-beta (2025-07-23)


### Features

- Added support for Collaborator resources to track repository collaborators
- Implemented Collaborator webhook processor for real-time updates


## 1.0.9-beta (2025-07-22)


### Improvements

- Made the `repos` field optional in the file selector configuration. When omitted, the file selector will apply to all repositories.


## 1.0.8-beta (2025-07-20)


### Improvements

- Bumped ocean version to ^0.26.1


## 1.0.7-beta (2025-07-16)


### Improvements

- Bumped ocean version to ^0.25.5


## 1.0.6-beta (2025-07-09)


### Improvements

- Gracefully handle permission error when fetching external identities fail
- Properly handle ignoring default errors in graphql client


## 1.0.5-beta (2025-07-09)


### Bugfix

- Fix default resources not getting created due to blueprint config error


## 1.0.4-beta (2025-07-08)


### Improvements

- Fix deleted raw results in file webhook processor and improved logging in repository visibility type


## 1.0.3-beta (2025-07-08)


### Bug Fixes

- Fix Bug on GraphQL Errors throwing a stack of errors instead of specific error messages


## 1.0.2-beta (2025-07-08)


### Improvements

- Temporally trim default resources to just repository and pull request


## 1.0.1-beta (2025-07-07)


### Improvements

- Bumped ocean version to ^0.25.0


## 1.0.0-beta (2025-07-04)


### Release

- Bumped integration from dev to beta release


## 0.5.2-dev (2025-07-03)


### Bug Fixes

- Fixed error handling for repositories with Advanced Security or Dependabot disabled
- Previously, 403 errors for disabled features would crash the integration
- Now gracefully ignores these errors and returns empty results
- Affects both code scanning alerts, Dependabot alerts exporters and webhook upsertion


## 0.5.1-dev (2025-07-02)


### Improvements

- Bumped ocean version to ^0.24.22


## 0.5.0-dev (2025-07-01)


### Features

- Added file exporter functionality with support for file content fetching and processing
- Implemented file webhook processor for real-time file change detection and processing
- Added file entity processor for dynamic file content retrieval in entity mappings
- Added support for file pattern matching with glob patterns and size-based routing (GraphQL vs REST)


## 0.4.0-dev (2025-06-26)


### Features

- Added support for Github folder kind


## 0.3.1-dev (2025-06-30)


### Improvements

- Bumped ocean version to ^0.24.21


## 0.3.0-dev (2025-06-26)


### Improvements

- Added dev suffix to version number


## 0.3.0-dev (2025-06-25)


### Features

- Added support for User kinds
- Added support for Team kinds


## 0.2.11 (2025-06-26)


### Improvements

- Bumped ocean version to ^0.24.20


## 0.2.10 (2025-06-25)


### Improvements

- Bumped ocean version to ^0.24.19


## 0.2.9 (2025-06-24)


### Improvements

- Bumped ocean version to ^0.24.18


## 0.2.8 (2025-06-23)


### Improvements

- Bumped ocean version to ^0.24.17


## 0.2.7 (2025-06-22)


### Improvements

- Bumped ocean version to ^0.24.16


## 0.2.6 (2025-06-22)


### Improvements

- Upgraded integration requests dependency (#1)


## 0.2.5-dev (2025-06-22)


### Improvements

- Bumped ocean version to ^0.24.15


## 0.2.4-dev (2025-06-22)


### Improvements

- Bumped ocean version to ^0.24.12


## 0.2.3-dev (2025-06-22)


### Improvements

- Bumped ocean version to ^0.24.12


## 0.2.2-dev (2025-06-16)


### Improvements

- Bumped ocean version to ^0.24.11


## 0.2.1-dev (2025-06-15)


### Improvements

- Bumped ocean version to ^0.24.10


## 0.2.0-dev (2025-06-13)


### Features

- Added support for Github workflows
- Added support support for Github workflow runs
- Implemented webhook processors for Workflow runs and workflows for real-time updates


## 0.1.17-dev (2025-06-13)


### Features

- Added support for Dependabot alerts and Code Scanning alerts with state-based filtering
- Implemented Dependabot alert and Code Scanning alert webhook processor for real-time updates


## 0.1.16-dev (2025-06-13)


### Features

- Added support for Environment resources to track repository environments
- Added support for Deployment resources with environment tracking
- Implemented deployment and environment webhook processors for real-time updates


## 0.1.15-dev (2025-06-12)


### Features

- Added support for Tag resources to track repository tags
- Added support for Release resources with state-based filtering (created, edited, deleted)
- Added support for Branch resources to track repository branches
- Implemented tag, release, and branch webhook processors for real-time updates


## 0.1.14-dev (2025-06-11)


### Improvements

- Added support for Issue resources with state-based filtering (open, closed, all)
- Implemented issue webhook processor for real-time updates


## 0.1.13-dev (2025-06-11)


- Added support for Pull Request resources with state-based filtering (open, closed, all)
- Implemented pull request webhook processor for real-time updates


## 0.1.12-dev (2025-06-11)


### Improvements

- Bumped ocean version to ^0.24.8


## 0.1.11-dev (2025-06-11)


### Improvements

- Bumped ocean version to ^0.24.7


## 0.1.10-dev (2025-06-09)


### Improvements

- Bumped ocean version to ^0.24.6


## 0.1.9-dev (2025-06-09)


### Improvements

- Bumped ocean version to ^0.24.5


## 0.1.8-dev (2025-06-09)


### Improvements

- Bumped ocean version to ^0.24.4


## 0.1.7-dev (2025-06-08)


### Improvements

- Bumped ocean version to ^0.24.3


## 0.1.6-dev (2025-06-04)

### Improvements

- Bumped ocean version to ^0.24.2


## 0.1.5-dev (2025-06-03)


### Improvements

- Bumped ocean version to ^0.24.1


## 0.1.4-dev (2025-06-03)


### Improvements

- Bumped ocean version to ^0.24.0


## 0.1.3-dev (2025-06-01)

### Improvements

- Bumped ocean version to ^0.23.5


## 0.1.2-dev (2025-05-30)


### Bug Fixes

- Fix timezone inconsistency issue while checking for expired Github App token (PORT-14913)

### Improvements

- Removed `Optional` from `AbstractGithubExporter` options to enforce stricter type adherence for concrete exporters.


## 0.1.1-dev (2025-05-29)

### Improvements

- Bumped ocean version to ^0.23.4


## 0.1.0-dev (2025-05-28)

### Features

- Created GitHub Ocean integration with support for Repository
- Added support for repository webhook event processor
- Add Tests for client and base webhook processor
- Added support for authenticating as a GitHub App
