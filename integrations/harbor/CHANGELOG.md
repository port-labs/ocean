# Changelog - Ocean - harbor

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-10-16

### Added
- Complete Harbor integration with Projects, Users, Repositories, and Artifacts
- Robot account authentication with token expiration handling
- Basic authentication support for local users
- Real-time webhook support for Harbor events (PUSH_ARTIFACT, DELETE_ARTIFACT, SCANNING_COMPLETED)
- Comprehensive filtering capabilities for all resource types
- Async HTTP client with pagination and rate limiting
- Production-ready error handling and logging
- Comprehensive test suite with 32 passing tests
- Type-safe code with full mypy compliance
- Code quality tools integration (ruff, black, mypy)

### Features
- **Projects**: Fetch and filter by visibility and name prefix
- **Users**: Fetch and filter by username prefix
- **Repositories**: Fetch and filter by project with automatic project name enrichment
- **Artifacts**: Fetch and filter by tag, digest, label, media type, and creation date
- **Webhooks**: Real-time event processing with signature validation
- **Authentication**: Support for both robot accounts and local user credentials
- **Error Handling**: Graceful handling of token expiration and API errors

### Technical Details
- Singleton pattern Harbor client for efficient resource usage
- Async/await patterns throughout for optimal performance
- Port relations system integration for efficient entity linking
- Comprehensive test coverage with mocked Harbor responses
- Production-ready logging and error handling
- Full type annotation compliance

<!-- towncrier release notes start -->
