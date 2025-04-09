# Changelog - Ocean - gitlab-v2

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.6-dev (2025-04-09)


### Improvements

- Added file enrichment functionality to associate include repository data
- Added filtering for merge requests to only fetch opened ones
- Enhanced concurrency control with proper semaphores and rate limiting

### Bug Fixes

- Updated default branch from "default" to "main" in FilesResourceConfig


## 0.1.5-dev (2025-04-09)


### Features

- Added support for folder kind


## 0.1.4-dev (2025-04-08)


### Features

- Added support for file kind


## 0.1.3-dev (2025-04-07)


### Improvements

- Bumped ocean version to ^0.22.2


## 0.1.2-dev (2025-04-03)


### Features

- Added support for live events


## 0.1.1-dev (2025-04-03)


### Improvements

- Bumped ocean version to ^0.22.1


## 0.1.0-dev (2025-02-27)


### Features

- Initial release of the GitLab v2 integration
- Support for syncing:
  - Groups
  - Projects
  - Issues
  - Merge Requests
