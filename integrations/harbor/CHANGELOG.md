# Changelog - Ocean - harbor-server

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

<!-- towncrier release notes start -->
### Added

#### Core Features:

- **Harbor API Client** - Comprehensive async client for Harbor API v2.0
  - Support for projects, repositories, artifacts, users, and webhooks
  - Built-in pagination support for all list endpoints
  - Rate limiting and retry logic with exponential backoff
  - Configurable concurrent request management
  - SSL certificate verification support
  
- **Real-time Webhook Support**
  - Automatic webhook registration for all accessible projects
  - Support for artifact push, delete, and scan completion events
  - Support for project and repository lifecycle events
  - Webhook orchestration with permission checks
  - Cleanup methods for webhook removal during uninstallation

- **Resource Synchronization**
  - Full resync support for projects, users, repositories, and artifacts
  - Batch processing with configurable page sizes
  - Concurrent artifact fetching for improved performance
  - Automatic enrichment of artifacts with project and repository context

- **Configuration Management**
  - Flexible selectors for filtering resources
  - Project selector with query support and metadata inclusion
  - User selector with system user filtering
  - Repository selector with project-level filtering
  - Artifact selector with vulnerability and build history options
  - Configurable page sizes for all resource types
