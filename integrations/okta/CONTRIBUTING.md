# Contributing to Okta Integration

Thank you for your interest in contributing to the Okta integration! This document provides guidelines and information for contributors.

## Development Setup

### Prerequisites

- Python 3.12+
- Poetry
- Docker (optional, for container testing)

### Getting Started

1. Clone the repository:
   ```bash
   git clone https://github.com/port-labs/ocean.git
   cd ocean/integrations/okta
   ```

2. Install dependencies:
   ```bash
   make install
   ```

3. Set up your development environment:
   ```bash
   make dev-install
   ```

## Development Workflow

### Running Tests

```bash
# Run all tests
make test

# Run specific test file
poetry run pytest tests/test_sample.py -v

# Run tests with coverage
poetry run pytest --cov=okta tests/ --cov-report=html
```

### Code Formatting and Linting

```bash
# Check code formatting
make lint

# Auto-format code
make format
```

### Running the Integration Locally

```bash
# Start the integration for development
make run
```

### Environment Variables

Create a `.env` file in the integration directory:

```env
OKTA_DOMAIN=dev-123456.okta.com
OKTA_API_TOKEN=your_test_token_here
PORT_CLIENT_ID=your_port_client_id
PORT_CLIENT_SECRET=your_port_client_secret
```

## Code Style

- Follow PEP 8 Python style guidelines
- Use type hints for all function parameters and return values
- Write descriptive docstrings for classes and functions
- Keep functions small and focused on a single responsibility
- Use meaningful variable and function names

### Example Code Style

```python
from typing import List, Dict, Any, Optional
from loguru import logger

class OktaClient:
    """Client for interacting with Okta API"""
    
    def __init__(self, domain: str, api_token: str) -> None:
        """Initialize Okta client.
        
        Args:
            domain: Okta domain (e.g., dev-123456.okta.com)
            api_token: Okta API token for authentication
        """
        self.domain = domain
        self.api_token = api_token
    
    async def get_users(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """Fetch users from Okta API.
        
        Args:
            limit: Maximum number of users to fetch
            
        Returns:
            List of user objects from Okta API
            
        Raises:
            OktaAPIError: If API request fails
        """
        logger.info(f"Fetching users with limit: {limit}")
        # Implementation here
        return []
```

## Testing

### Test Structure

- Unit tests: Test individual functions and methods
- Integration tests: Test interaction with external APIs
- Mock external dependencies in unit tests
- Use fixtures for common test data

### Writing Tests

```python
import pytest
from unittest.mock import AsyncMock, patch
from okta.client import OktaClient

class TestOktaClient:
    """Test cases for Okta client"""
    
    @pytest.fixture
    def okta_client(self):
        """Fixture providing configured Okta client"""
        return OktaClient("test.okta.com", "test_token")
    
    @pytest.mark.asyncio
    async def test_get_users_success(self, okta_client):
        """Test successful user retrieval"""
        with patch.object(okta_client, '_make_request') as mock_request:
            mock_request.return_value = [{"id": "user1", "profile": {"email": "test@example.com"}}]
            
            users = await okta_client.get_users()
            
            assert len(users) == 1
            assert users[0]["id"] == "user1"
            mock_request.assert_called_once_with("/users", params={})
```

## Documentation

### Code Documentation

- Add docstrings to all public functions and classes
- Include parameter descriptions and return value information
- Document any exceptions that might be raised
- Use type hints consistently

### README Updates

When adding new features:

1. Update the feature list in README.md
2. Add configuration examples if new options are introduced
3. Update the troubleshooting section if needed
4. Add examples for new functionality

## Submitting Changes

### Pull Request Process

1. Create a feature branch from `main`:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes and commit them:
   ```bash
   git add .
   git commit -m "Add: Description of your changes"
   ```

3. Run tests and linting:
   ```bash
   make ci
   ```

4. Push your branch:
   ```bash
   git push origin feature/your-feature-name
   ```

5. Create a pull request with:
   - Clear description of changes
   - Reference to related issues
   - Screenshots if UI changes are involved
   - Test coverage information

### Commit Message Format

Use conventional commit format:

```
<type>: <description>

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat: add support for custom user attributes
fix: handle rate limiting errors properly
docs: update installation instructions
```

## Release Process

### Version Numbering

Follow [Semantic Versioning](https://semver.org/):
- `MAJOR.MINOR.PATCH`
- Major: Breaking changes
- Minor: New features (backward compatible)
- Patch: Bug fixes (backward compatible)

### Creating a Release

1. Update version in `pyproject.toml`
2. Update CHANGELOG.md with new version
3. Create release commit
4. Tag the release
5. Push changes and tags

## Getting Help

- Join our [Slack community](https://getport.io/community)
- Check existing [GitHub issues](https://github.com/port-labs/ocean/issues)
- Read the [Port documentation](https://docs.getport.io/)

## Code of Conduct

Please follow our code of conduct in all interactions:
- Be respectful and inclusive
- Provide constructive feedback
- Focus on the technical aspects
- Help others learn and grow