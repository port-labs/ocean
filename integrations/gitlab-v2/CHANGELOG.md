# Changelog - Ocean - gitlab-v2

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.26 (2025-06-09)


### Improvements

- Bumped ocean version to ^0.24.6


## 0.1.25 (2025-06-09)


### Improvements

- Bumped ocean version to ^0.24.5


## 0.1.24 (2025-06-09)


### Improvements

- Bumped ocean version to ^0.24.4


## 0.1.23 (2025-06-08)


### Improvements

- Bumped ocean version to ^0.24.3


## 0.1.22 (2025-06-05)

- Graceful handling of HTTP error codes (401, 403, 404) to prevent resync failures


## 0.1.21 (2025-06-04)

### Improvements

- Bumped ocean version to ^0.24.2


## 0.1.20 (2025-06-03)


### Improvements

- Bumped ocean version to ^0.24.1


## 0.1.19 (2025-06-03)


### Improvements

- Bumped ocean version to ^0.24.0


## 0.1.18 (2025-06-01)


### Improvements

- transfer the integration to GA phase


## 0.1.17 (2025-06-01)


### Improvements

- Bumped ocean version to ^0.23.5


## 0.1.16 (2025-05-29)


### Improvements

- Bumped ocean version to ^0.23.4


## 0.1.15 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.3


## 0.1.14 (2025-05-28)


### Improvements

- Added Helm deployment method override configuration to spec.yaml


## 0.1.13 (2025-05-28)


### Improvements

- Bumped ocean version to ^0.23.2


## 0.1.12 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.1


## 0.1.11 (2025-05-27)


### Improvements

- Bumped ocean version to ^0.23.0


## 0.1.10 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.12


## 0.1.9 (2025-05-26)


### Improvements

- Bumped ocean version to ^0.22.11


## 0.1.8 (2025-05-20)


### Improvements

- Bumped ocean version to ^0.22.10


## 0.1.7 (2025-05-19)


### Improvements

- Bumped ocean version to ^0.22.9


## 0.1.5 (2025-05-15)


### Improvements

- Bumped ocean version to ^0.22.8


## 0.1.4 (2025-05-12)


### Improvements

- Bumped ocean version to ^0.22.7


## 0.1.3 (2025-05-06)


### Improvements

- Bumped ocean version to ^0.22.6


## 0.1.2 (2025-04-28)

### Improvements

- Added title to the integration to be viewed in the data sources page


## 0.1.1 (2025-04-27)

### Bug Fixes

- Resolved "h11 accepts some malformed Chunked-Encoding bodies" h11 vulnerability


### Improvements

- Bumped ocean version to ^0.22.5


## 0.1.0 (2025-23-04)


### Improvement

- Bumped integration version from beta to GA


## 0.1.2-beta (2025-04-17)


### Improvements

- Adds Groups, Members and Merge Requests to integration defaults


## 0.1.1-beta (2025-04-17)


### Bug Fixes

- Fixed integration icon


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
