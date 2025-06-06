# Spacelift Ocean Integration

A comprehensive Ocean integration for Spacelift that provides real-time data synchronization for Spaces, Stacks, Deployments (Runs), Policies, and Users.

## Features

- **Smart Rate Limiting**: Intelligent rate limiting with retry-after header support and configurable intervals
- **Automatic Token Management**: JWT token lifecycle management with automatic refresh
- **Reusable Pagination**: Cursor-based pagination for all resource types
- **Comprehensive Error Handling**: Authentication retry, network error recovery, and graceful degradation
- **Ocean Compliance**: Full integration with Port Ocean framework patterns and best practices

## Quick Start

### Prerequisites

- Python 3.12+
- Poetry for dependency management
- Spacelift API credentials

### Installation

```bash
# Install dependencies
make install

# Install with local Ocean core for development
make install/local-core
```

### Configuration

Set the following environment variables:

```bash
export SPACELIFT_API_ENDPOINT="https://your-account.app.spacelift.io/graphql"
export SPACELIFT_API_KEY_ID="your-api-key-id"
export SPACELIFT_API_KEY_SECRET="your-api-key-secret"
export SPACELIFT_ACCOUNT_NAME="your-account-name"
export SPACELIFT_MAX_RETRIES="3"  # Optional, defaults to 2
```

### Running the Integration

```bash
# Start the integration
make run
```

## Development

### Code Quality

```bash
# Run all linting checks
make lint

# Auto-fix linting issues
make lint/fix
```

### Testing

The integration includes comprehensive tests with different execution options:

```bash
# Run all tests (includes both passing and Ocean-dependent tests)
make test

# Run only unit tests (all passing tests)
make test/unit

# Run only integration tests (requires Ocean context)
make test/integration
```

#### Test Coverage

| Test Suite            | Status                    | Tests                             | Coverage                                         |
| --------------------- | ------------------------- | --------------------------------- | ------------------------------------------------ |
| **Unit Tests**        | ✅ **46/46 PASSING**      | `test_client.py`, `test_utils.py` | Client logic, data normalization, URL generation |
| **Integration Tests** | ❌ Ocean Context Required | `test_main.py`                    | Ocean integration handlers, resource sync logic  |

**Recommended**: Use `make test/unit` for development and CI/CD as these tests provide comprehensive coverage of all business logic without Ocean framework dependencies.

#### Test Features

- **Concurrent Execution**: Tests run in parallel using `pytest-xdist`
- **Async Support**: Full async/await test patterns with `pytest-asyncio`
- **Comprehensive Mocking**: Isolated testing of all components
- **User-Friendly Output**: Clear test results with status indicators

### Project Structure

```
spacelift/
├── spacelift/                 # Main integration package
│   ├── client.py             # Spacelift GraphQL client
│   ├── utils.py              # Utilities and helpers
│   └── __init__.py
├── tests/                    # Test suite
│   ├── test_client.py        # Client tests (✅ passing)
│   ├── test_utils.py         # Utils tests (✅ passing)
│   ├── test_main.py          # Ocean integration tests (requires context)
│   └── conftest.py           # Test configuration
├── main.py                   # Ocean integration entry point
├── Makefile                  # Development commands
├── pyproject.toml            # Project configuration
└── README.md                 # This file
```

### Key Components

#### SpaceliftClient (`spacelift/client.py`)

Production-ready GraphQL client with:

- **Authentication**: JWT token management with automatic refresh
- **Rate Limiting**: Smart detection and handling of API limits
- **Pagination**: Cursor-based pagination for all resource types
- **Error Handling**: Comprehensive retry logic and error classification
- **Async Context Manager**: Proper resource lifecycle management

#### Utils (`spacelift/utils.py`)

Utility functions for:

- **Data Normalization**: Consistent data processing and type conversion
- **URL Generation**: Resource-specific URL construction
- **Resource Types**: Type-safe resource kind enumeration

#### Ocean Integration (`main.py`)

Ocean framework integration providing:

- **Resource Handlers**: Sync handlers for all Spacelift resource types
- **Data Processing**: Resource normalization and URL enrichment
- **Error Handling**: Graceful error handling and logging

## API Resources

| Resource        | Description                               | Fields                                                      |
| --------------- | ----------------------------------------- | ----------------------------------------------------------- |
| **Spaces**      | Spacelift spaces and organizational units | ID, name, description, labels, parent space                 |
| **Stacks**      | Infrastructure stacks and configurations  | ID, name, space, repository, provider, state, tracked runs  |
| **Deployments** | Stack runs and deployment history         | ID, type, state, commit info, triggered by, drift detection |
| **Policies**    | Access and approval policies              | ID, name, type, space, body, labels                         |
| **Users**       | Account users and permissions             | ID, username, email, admin status, last seen                |

## Configuration Options

| Variable                   | Description                     | Required | Default |
| -------------------------- | ------------------------------- | -------- | ------- |
| `SPACELIFT_API_ENDPOINT`   | GraphQL API endpoint            | ✅       | -       |
| `SPACELIFT_API_KEY_ID`     | API key identifier              | ✅       | -       |
| `SPACELIFT_API_KEY_SECRET` | API key secret                  | ✅       | -       |
| `SPACELIFT_ACCOUNT_NAME`   | Account name for URL generation | ✅       | -       |
| `SPACELIFT_MAX_RETRIES`    | Maximum retry attempts          | ❌       | 2       |

## Troubleshooting

### Common Issues

1. **Authentication Errors**: Verify API credentials and endpoint URL
2. **Rate Limiting**: Integration automatically handles rate limits with exponential backoff
3. **Token Expiry**: Tokens are automatically refreshed before expiration

### Debugging

Enable debug logging:

```bash
export LOG_LEVEL=DEBUG
make run
```

### Support

For issues and questions:

1. Check the [Ocean documentation](https://ocean.getport.io)
2. Review test examples in the `tests/` directory
3. Examine client implementation in `spacelift/client.py`

## Contributing

1. Install development dependencies: `make install`
2. Run tests: `make test/unit`
3. Run linting: `make lint`
4. Submit pull request

## License

[Add your license information here]
