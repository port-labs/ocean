# Changelog - Ocean - azure-ms

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.37-beta (2026-01-14)


### Improvements

- Bumped ocean version to ^0.32.11


## 0.2.36-beta (2026-01-11)


### Improvements

- Bumped ocean version to ^0.32.10


## 0.2.35-beta (2025-12-25)


## Bug Fixes

- Fixed spec.yaml conventions


## 0.2.34-beta (2025-12-24)


### Improvements

- Bumped ocean version to ^0.32.9


## 0.2.33-beta (2025-12-23)


### Improvements

- Bumped ocean version to ^0.32.8


## 0.2.32-beta (2025-12-22)


### Improvements

- Bumped ocean version to ^0.32.7


## 0.2.31-beta (2025-12-18)


### Improvements

- Bumped ocean version to ^0.32.5


## 0.2.30-beta (2025-12-16)


### Improvements

- Bumped ocean version to ^0.32.4


## 0.2.29-beta (2025-12-15)


### Improvements

- Bumped ocean version to ^0.32.3


## 0.2.28-beta (2025-12-14)


### Improvements

- Bumped ocean version to ^0.32.2


## 0.2.27-beta (2025-12-10)


### Improvements

- Bumped ocean version to ^0.32.1


## 0.2.26-beta (2025-12-09)


### Improvements

- Bumped ocean version to ^0.32.0


## 0.2.25-beta (2025-12-09)


### Improvements

- Bumped ocean version to ^0.31.7


## 0.2.24-beta (2025-12-09)


### Improvements

- Bumped ocean version to ^0.31.6


## 0.2.23-beta (2025-12-08)


### Improvements

- Bumped ocean version to ^0.31.4


## 0.2.22-beta (2025-12-08)


### Improvements

- Bumped ocean version to ^0.31.3


## 0.2.21-beta (2025-12-07)


### Improvements

- Bumped ocean version to ^0.31.2


## 0.2.20-beta (2025-12-04)


### Improvements

- Bumped ocean version to ^0.31.1


## 0.2.19-beta (2025-12-04)


### Improvements

- Bumped ocean version to ^0.31.0


## 0.2.18-beta (2025-12-03)


### Improvements

- Bumped ocean version to ^0.30.7


## 0.2.17-beta (2025-12-01)


### Improvements

- Bumped ocean version to ^0.30.6


## 0.2.16-beta (2025-11-27)


### Improvements

- Bumped ocean version to ^0.30.5


## 0.2.15-beta (2025-11-26)


### Improvements

- Bumped ocean version to ^0.30.4


## 0.2.14-beta (2025-11-25)


### Improvements

- Bumped ocean version to ^0.30.3


## 0.2.13-beta (2025-11-24)


### Improvements

- Bumped ocean version to ^0.30.2


## 0.2.12-beta (2025-11-23)


### Improvements

- Bumped ocean version to ^0.30.1


## 0.2.11-beta (2025-11-23)


### Improvements

- Bumped ocean version to ^0.30.0


## 0.2.10-beta (2025-11-23)


### Improvements

- Bumped ocean version to ^0.29.10


## 0.2.9-beta (2025-11-20)


### Improvements

- Bumped ocean version to ^0.29.9


## 0.2.8-beta (2025-11-19)


### Improvements

- Bumped ocean version to ^0.29.8


## 0.2.7-beta (2025-11-18)


### Improvements

- Bumped ocean version to ^0.29.7


## 0.2.6-beta (2025-11-17)


### Improvements

- Bumped ocean version to ^0.29.6


## 0.2.5-beta (2025-11-10)


### Improvements

- Bumped ocean version to ^0.29.5


## 0.2.4-beta (2025-11-10)


### Improvements

- Bumped ocean version to ^0.29.4


## 0.2.3-beta (2025-11-09)


### Improvements

- Bumped starlette version to 0.49.3
- Bumped aiohttp version to 3.13.2

## 0.2.2-beta (2025-11-09)


### Improvements

- Bumped ocean version to ^0.29.3


## 0.2.1-beta (2025-11-09)


### Improvements

- Bumped ocean version to ^0.29.2


## 0.2.0-beta (2025-10-23)


### Improvements

- Added an Adaptive Token Bucket Rate Limiter, which intelligently adjusts its refill rate and request limiting in real time based on feedback from Azure API responses. This improvement enhances performance and more gracefully handles Azure rate limiting.
- Refactored API request handling to use Port's httpx client instead of the Azure SDK. This reduces resource usage and eliminates the overhead of managing multiple client contexts concurrently.
- Azure typically returns around 1,000 entities per Resource Graph request. This release implementes a buffering mechanism to yield results in batches of 100, reducing the processing load on Ocean Core.

## Breaking Changes

- The `resource` and `resourceContainer` Kinds have been revamped, enabling users to perform advanced queries through `graphQuery` selector thereby fully leveraging all features of the Azure Resource Graph API.

## Bug Fixes

- Fixed mapping to follow standard conventions


## 0.1.8-beta (2025-11-06)


## Bug Fixes

- Bumped ocean version to ^0.29.1


## 0.1.7-beta (2025-11-04)


### Improvements

- Bumped ocean version to ^0.29.0


## 0.1.6-beta (2025-11-02)


### Improvements

- Bumped ocean version to ^0.28.19


## 0.1.5-beta (2025-10-27)


### Improvements

- Bumped ocean version to ^0.28.18


## 0.1.4-beta (2025-10-26)


### Improvements

- Bumped ocean version to ^0.28.17


## 0.1.3-beta (2025-10-21)


### Improvements

- Bumped ocean version to ^0.28.16


## 0.1.2-beta (2025-10-20)


### Improvements

- Bumped ocean version to ^0.28.15


## 0.1.1-beta (2025-10-15)


### Improvements

- Bumped ocean version to ^0.28.14


## 0.1.0-beta (2025-10-14)

### Improvements

- Upgrade integration to Beta


## 0.1.0-dev (2025-04-15)

### Features

- Implemented the Azure multi subscription ocean integration (0.1.0)
