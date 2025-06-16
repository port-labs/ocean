# Changelog - Ocean - github

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

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
