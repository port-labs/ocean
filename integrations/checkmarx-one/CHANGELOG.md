# Changelog - Ocean - checkmarx_one

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## 0.1.0-dev  (2025-08-07)
# Changelog - Ocean - checkmarx_one

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## [0.1.0-dev] - 2024-12-19

### Added
- Initial release of Checkmarx One integration
- Support for Checkmarx One projects synchronization
- Support for Checkmarx One scans synchronization with project filtering
- Support for Checkmarx One scan results synchronization with comprehensive filtering options
- Async HTTP client implementation for efficient API communication
- Rate limiting support via aiolimiter
- Comprehensive error handling and logging
- Resource configuration with flexible selectors for scans and scan results
- Pagination support for large datasets
- Type-safe configuration using Pydantic models

### Features
- **Project Management**: Full synchronization of Checkmarx One projects
- **Scan Management**: Synchronization of scans with project-based filtering
- **Scan Results**: Detailed scan results with configurable filtering by:
  - Severity levels
  - State
  - Status
  - Result types (with exclusion support)
  - Sorting options
- **Flexible Configuration**: Support for custom selectors and resource configurations
- **Performance Optimized**: Async operations with proper pagination and rate limiting

### Technical Details
- Built with Python 3.12+
- Uses Port Ocean framework v0.27.0+
- Implements async generators for memory-efficient data processing
- Comprehensive test suite with pytest
- Type checking with mypy
- Code formatting with black and ruff
- Documentation with towncrier for changelog management

<!-- towncrier release notes end -->
