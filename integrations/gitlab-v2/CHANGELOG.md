# Changelog - Ocean - gitlab-v2

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0-beta (2025-04-15)


### Improvement

- Bumped integration version from dev to beta


## 0.1.13-dev (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.4


## 0.1.12-dev (2025-04-15)


### Improvements

- Bumped ocean version to ^0.22.3
- Updated service blueprint schema with new fields:
  - readme (markdown format)
  - language
  - slack (URL format)
  - tier (enum with colors)
- Removed description and defaultBranch fields from service blueprint


## 0.1.11-dev (2025-04-14)



### Improvements

- Enhanced webhook processing with `GitlabLiveEventsProcessorManager` to utilize the `GitManipulationHandler` for Entity Processing

### Bug Fixes

- Renamed 'hook' class attribute to 'hooks' in file and folder webhook processors


## 0.1.10-dev (2025-04-14)


### Features

- Added support for pipeline and job kinds

### Improvements

- Added email field to group member enrichment for better user identification


## 0.1.9-dev (2025-04-14)


### Features

- Add support for gitlab members


## 0.1.8-dev (2025-04-14)


### Features

- Added support for live events for folder kind


## 0.1.7-dev (2025-04-14)


### Improvements

- Added support for resolving `file://` references in parsed JSON and YAML files.


## 0.1.6-dev (2025-04-09)


### Features

- Added support for live events for file kind

### Improvements

- Added file enrichment
- Added filtering for merge requests
- Enhanced concurrency control

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
