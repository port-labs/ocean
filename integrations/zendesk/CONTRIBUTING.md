# Contributing to Zendesk Integration

Thank you for your interest in contributing to the Zendesk integration for Port Ocean!

## Development Setup

### Prerequisites
- Python 3.12+
- Poetry for dependency management
- Access to a Zendesk test environment

### Local Setup
1. Clone the repository
2. Navigate to the integration directory:
   ```bash
   cd integrations/zendesk
   ```
3. Install dependencies:
   ```bash
   make install
   ```
4. Set up your test configuration
5. Run tests to ensure everything works:
   ```bash
   make test
   ```

### Running Locally
To run the integration locally for testing:
```bash
make run
```

This will start the integration in debug mode using `debug.py`.

## Development Guidelines

### Code Style
- Follow Ocean integration patterns and conventions
- Use async/await for all I/O operations
- Implement comprehensive error handling
- Add type hints to all functions
- Follow PEP 8 style guidelines

### Testing
- Write tests for all new functionality
- Maintain high test coverage
- Use the provided fixtures in `conftest.py`
- Test both success and error scenarios
- Mock external API calls

### API Integration
- Follow Zendesk API best practices
- Implement proper rate limiting
- Handle pagination for large datasets
- Use API token authentication
- Document API endpoints used with URLs

### Documentation
- Update README.md for new features
- Document configuration parameters
- Include example usage
- Reference official Zendesk documentation
- Update CHANGELOG.md for all changes

## Code Comments

When adding code that interacts with Zendesk API, include multiline comments explaining:
- Source documentation URLs
- Purpose of the code block
- Expected return values/behavior

Example:
```python
"""
Fetch tickets from Zendesk API with pagination

Based on: https://developer.zendesk.com/api-reference/ticketing/tickets/tickets/

Purpose: Retrieve all tickets from Zendesk with proper pagination handling
Expected output: Async generator yielding batches of ticket data dictionaries
"""
async def get_paginated_tickets(self, params):
    # Implementation here
```

## Supported Resources

This integration focuses on four main Zendesk domain objects:
- **ticket** - Support tickets
- **side_conversation** - Side conversations within tickets
- **user** - Users (all types)
- **organization** - Organizations/companies

## Testing

### Unit Tests
Test individual components in isolation:
```bash
pytest tests/test_client.py
pytest tests/test_webhook_processors.py
```

### Integration Tests  
Test the full integration flow:
```bash
pytest tests/test_sample.py
```

### Manual Testing
1. Set up test Zendesk environment
2. Configure integration with test credentials
3. Run full sync and verify data
4. Test webhook events if possible

## Submitting Changes

### Pull Request Process
1. Create a feature branch from main
2. Make your changes following the guidelines above
3. Add/update tests for your changes
4. Update documentation as needed
5. Update CHANGELOG.md
6. Submit a pull request with:
   - Clear description of changes
   - Links to relevant Zendesk documentation
   - Testing instructions
   - Screenshots if UI changes

### Pull Request Template
Include in your PR description:
- **Summary**: Brief description of changes
- **API References**: Links to Zendesk docs used
- **Testing**: How to test the changes
- **Configuration**: Any new config parameters
- **Breaking Changes**: If any

## API Documentation References

Always reference official Zendesk documentation:
- [API Reference](https://developer.zendesk.com/api-reference/introduction/introduction/)
- [Rate Limits](https://developer.zendesk.com/api-reference/introduction/rate-limits/)
- [Authentication](https://developer.zendesk.com/api-reference/introduction/security-and-auth/)
- [Webhooks](https://developer.zendesk.com/api-reference/webhooks/webhooks-api/webhooks/)

## Common Development Tasks

### Adding New Resource Types
1. Add to `kinds.py`
2. Implement client methods in `zendesk/client.py`
3. Add resync handler in `main.py`
4. Create webhook processor if needed
5. Add tests and documentation

### Adding New Webhook Events
1. Add event types to appropriate webhook processor
2. Implement event handling logic
3. Add tests for the new events
4. Document webhook setup requirements

### Performance Optimization
- Use async generators for large datasets
- Implement proper pagination
- Respect rate limits
- Use concurrent requests judiciously
- Monitor memory usage

## Questions and Support

For questions about:
- **Zendesk API**: Refer to official documentation
- **Ocean Framework**: Check Ocean documentation
- **Integration-specific**: Open an issue in the repository

## Code of Conduct

Please follow the project's code of conduct and be respectful to all contributors.

Thank you for contributing to making this integration better!