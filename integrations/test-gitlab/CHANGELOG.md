# Changelog - Ocean - gitlab_v2

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0-beta] - 2024-11-13

### Added

- **Initial Implementation of GitLab Integration**: Added the core components for integrating with GitLab, including fetching data, handling webhooks, and syncing entities to Port.
- **AsyncFetcher Class**: Created `AsyncFetcher` class in `core/async_fetcher.py` to handle asynchronous fetching from GitLab.
- **Utility Functions**: Implemented utility functions in `core/utils.py` such as `parse_datetime`, `generate_entity_from_port_yaml`, and `load_mappings`.
- **GitLabHandler Class**: Developed `GitLabHandler` class in `client.py` to manage interactions with GitLab and Port, including fetching projects, handling webhooks, and syncing entities.
- **Main Application Logic**: Implemented main application logic in `main.py` to handle FastAPI routes and integration events, including webhook handling and resync logic.
- **Test Cases**: Added comprehensive test cases in `tests/test_client.py` and `tests/test_utils.py` to ensure the correctness of the integration.

### Changed

- **Initialization of PortOcean Context**: Refactored the initialization of the PortOcean context to ensure it is properly set up for testing and production use.
- **Mocking for Tests**: Used `AsyncMock` and `MagicMock` to mock asynchronous and synchronous calls in test cases, ensuring tests are isolated and reliable.
- **Error Handling**: Improved error handling for unsupported kinds and HTTP errors, providing meaningful error messages.

### Fixed

- **Type Errors in Tests**: Corrected type errors in test cases where `MagicMock` objects were used in `await` expressions by using `AsyncMock`.
- **Name Errors**: Resolved name errors related to the `jq` library by ensuring it is imported in test files.
- **Assertion Errors**: Fixed assertion errors in `test_generate_entity_from_port_yaml` by ensuring the expected result matches the actual result.
- **Connection Errors**: Mocked HTTP requests to avoid connection errors by using `AsyncMock` for asynchronous HTTP calls.
- **Pagination Logic**: Ensured that pagination logic correctly handles `MagicMock` objects by returning expected values.

### Removed

- **Deprecated Code**: Removed any deprecated or unused code to keep the project clean and maintainable.

### Security

- **Environment Variables**: Ensured that sensitive information such as tokens and URLs are managed through environment variables and configuration files.

### Performance

- **Efficient Data Fetching**: Optimized data fetching using asynchronous methods to improve performance and reduce latency.

### Documentation

- **README and Comments**: Added detailed comments in the code and README to explain the purpose and usage of each module and function.

### Dependencies

- **Added Dependencies**: Added necessary dependencies such as `gitlab`, `jq`, `pytest`, and `httpx` to the project.
