# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-12-19

### Features

- Initial release of Cursor integration for Port Ocean
- Support for syncing team information and member details
- Daily usage metrics tracking across teams
- AI commit metrics and tracking
- AI code changes monitoring  
- Usage events detailed logging
- User-specific usage patterns and statistics
- Configurable date ranges for historical data sync
- User email filtering for focused analytics
- Comprehensive error handling and retry logic
- Automatic pagination support for large datasets
- Integration with Port Ocean framework
- Complete test coverage for all components
- Example blueprints and mappings provided
- Comprehensive documentation and setup guide

### Added

- `CursorClient` - API client for Cursor Admin API
- Support for multiple entity types: teams, users, daily usage, AI commits, AI code changes, usage events
- Configurable sync parameters via Ocean integration config
- Robust error handling with exponential backoff retry
- Pagination support for API responses
- Metadata enrichment for all synced entities
- Custom date range configuration for different data types
- User filtering capabilities
- Comprehensive test suite with mocks and fixtures
- Development tooling (Makefile, linting, formatting)
- Documentation and examples