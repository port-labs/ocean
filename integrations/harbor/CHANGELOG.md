# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2025-10-30

### Added

- Initial release of GoHarbor integration for Port Ocean
- Support for syncing Harbor projects with filtering by visibility and name
- Support for syncing Harbor users with username filtering
- Support for syncing Harbor repositories with project and name filters
- Support for syncing Harbor artifacts with comprehensive filtering options:
  - Tag filtering
  - Digest filtering
  - Label filtering
  - Media type filtering
  - Vulnerability scan overview inclusion
- Real-time webhook support for artifact events:
  - Artifact pushed events
  - Artifact deleted events
  - Artifact pulled events
  - Vulnerability scan completed/failed events (assumed pattern)
- Automatic webhook registration for all projects on integration startup
- Pagination support for all resource types
- Rate limiting and concurrency control
- Comprehensive error handling and logging
- Relationship mapping between artifacts, repositories, and projects
- BasicAuth authentication support (admin users and robot accounts)

### Features

- **Projects**: Fetch all Harbor projects with optional public/private filtering
- **Users**: Fetch all Harbor users with optional username filtering
- **Repositories**: Fetch repositories across all projects or filtered by project name
- **Artifacts**: Fetch artifacts with scan results, tags, and labels
- **Webhooks**: Real-time updates for artifact lifecycle events
- **Performance**: Parallel fetching of repositories and artifacts across projects
- **Extensibility**: Generic design allows easy addition of new resource types

### Technical Details

- Built with Ocean framework using pure async/await patterns
- Uses Ocean's `http_async_client` for all HTTP requests
- Implements page-based pagination matching Harbor API v2.0
- Semaphore-based concurrency control (max 5 concurrent requests)
- Configurable selector-based filtering for all resource types
- Context enrichment for artifacts to enable proper relationship mapping

[0.1.0]: https://github.com/port-labs/ocean/releases/tag/goharbor-v0.1.0
