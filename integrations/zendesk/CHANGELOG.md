# Changelog

All notable changes to this integration will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2024-01-20

### Added
- Initial Zendesk integration with support for:
  - Tickets synchronization with filtering by status, priority, assignee, and organization
  - Users synchronization with filtering by role and organization  
  - Organizations synchronization with filtering by external ID
  - Groups synchronization with option to include deleted groups
  - Brands synchronization with option to include inactive brands
- Real-time webhook support for tickets, users, and organizations
- Authentication support for both API tokens and OAuth tokens
- Comprehensive error handling and rate limiting
- Full test coverage