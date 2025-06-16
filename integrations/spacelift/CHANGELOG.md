# Changelog - Ocean - spacelift

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->

## [0.1.0] - 2024-01-15

### Added
- Initial release of the Spacelift integration for Ocean
- Support for syncing Spacelift spaces, stacks, deployments, policies, and users
- Real-time webhook support for stack updates and deployment state changes
- GraphQL API client with authentication support
- Comprehensive error handling and fallback mechanisms
- Configurable pagination and retry logic

### Features
- **Resource Sync**: Full sync support for all Spacelift resource types
- **Real-time Updates**: Webhook endpoints for real-time stack and deployment updates
- **Error Resilience**: Graceful handling of API permission issues with simplified fallback queries
- **Flexible Configuration**: Environment-based configuration with customizable API endpoints and credentials
