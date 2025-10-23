# Changelog - Ocean - azure-ms

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.2.0-beta (2025-10-23)


### Improvements

- Added new azureCloudResource Kind, enabling users to perform advanced queries and fully leverage all features of the Azure Resource Graph API.
- Added an Adaptive Token Bucket Rate Limiter, which intelligently adjusts its refill rate and request limiting in real time based on feedback from Azure API responses. This improvement enhances performance and more gracefully handles Azure rate limiting.
- Refactored API request handling to use Port's httpx client instead of the Azure SDK. This reduces resource usage and eliminates the overhead of managing multiple client contexts concurrently.
- Azure typically returns around 1,000 entities per Resource Graph request. This release implementes a buffering mechanism to yield results in batches of 100, reducing the processing load on Ocean Core.

## Breaking Changes

- The resourceContainer and resource Kinds have been removed. Their functionality is now available through the new azureCloudResource Kind.

## Bug Fixes

- Fixed mapping to follow standard conventions


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
