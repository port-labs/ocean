# Changelog - Ocean - github

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

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
