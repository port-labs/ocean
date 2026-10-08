# Changelog

All notable changes to this integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-01-14

### Added

- Initial Harbor integration for Port using Ocean framework
- Support for syncing Harbor projects with configurable visibility filters
- Support for syncing Harbor users and their roles
- Support for syncing Harbor repositories with artifact counts
- Support for syncing Harbor artifacts with vulnerability scan results
- Webhook support for real-time updates:
  - PUSH_ARTIFACT events
  - DELETE_ARTIFACT events
  - SCANNING_COMPLETED events
  - SCANNING_FAILED events
- Webhook signature validation using HMAC-SHA256
- Configurable filters for projects (visibility, name prefix)
- Configurable filters for artifacts (minimum vulnerability severity)
- Pagination support for all Harbor API endpoints
- Parallel artifact fetching for improved performance
- Comprehensive test coverage with mocked Harbor responses
- Full async implementation using Ocean's HTTP client
- Detailed logging for all operations
- Support for both robot accounts and local user authentication

### Features

- Automatic resync of all Harbor entities
- Real-time webhook integration for immediate updates
- Vulnerability scanning insights in Port catalog
- Project, repository, and artifact relationship mapping
- Configurable SSL verification
- Rate limiting and retry logic with exponential backoff
- Structured logging for debugging and monitoring
