# Contributing to AWS-v3 Integration

Thank you for your interest in contributing to the AWS-v3 integration! This document provides guidelines and information for contributors.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Contributing Guidelines](#contributing-guidelines)
- [Adding New Resource Kinds](#adding-new-resource-kinds)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Pull Request Process](#pull-request-process)
- [Release Process](#release-process)

## Code of Conduct

This project follows the [Contributor Covenant Code of Conduct](https://www.contributor-covenant.org/). By participating, you are expected to uphold this code.

## Getting Started

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- AWS CLI configured with appropriate permissions
- Git

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/ocean.git
   cd ocean/integrations/aws-v3
   ```

2. **Install Dependencies**
   ```bash
   make install
   ```

3. **Set Up AWS Credentials**
   ```bash
   aws configure
   # Or set environment variables:
   export AWS_ACCESS_KEY_ID=your_key
   export AWS_SECRET_ACCESS_KEY=your_secret
   export AWS_DEFAULT_REGION=us-east-1
   ```

4. **Run Tests**
   ```bash
   poetry run pytest
   ```

## Contributing Guidelines

### Types of Contributions

We welcome several types of contributions:

- **Bug Fixes**: Fix existing issues and improve stability
- **New Resource Kinds**: Add support for new AWS services/resources
- **Enhancements**: Improve existing functionality
- **Documentation**: Improve guides, comments, and examples
- **Tests**: Add or improve test coverage
- **Performance**: Optimize existing code

### Before You Start

1. **Check Existing Issues**: Look for existing issues or discussions
2. **Create an Issue**: For significant changes, create an issue first
3. **Discuss Large Changes**: Reach out for feedback on major features
4. **Follow the Guide**: Use [ADDING_NEW_KINDS.md](./ADDING_NEW_KINDS.md) for new resource kinds

## Adding New Resource Kinds

### Quick Start

1. **Follow the Guide**: Use [ADDING_NEW_KINDS.md](./ADDING_NEW_KINDS.md) for step-by-step instructions
2. **Study Examples**: Look at existing implementations (S3, ECS, EC2)
3. **Test Thoroughly**: Ensure your implementation works with real AWS resources
4. **Update Documentation**: Add your resource to relevant documentation

### Resource Kind Checklist

- [ ] Added to `ObjectKind` enum in `types.py`
- [ ] Created models in `aws/core/exporters/{service}/{resource}/models.py`
- [ ] Implemented actions in `aws/core/exporters/{service}/{resource}/actions.py`
- [ ] Created exporter in `aws/core/exporters/{service}/{resource}/exporter.py`
- [ ] Added resync handler in `main.py`
- [ ] Updated `.port/spec.yaml`
- [ ] Added package `__init__.py`
- [ ] Written comprehensive tests
- [ ] Tested with real AWS resources
- [ ] Updated documentation

## Code Standards

### Python Style

We follow Python best practices and use several tools for code quality:

```bash
# Format code
poetry run black .

# Sort imports
poetry run isort .

# Type checking
poetry run mypy .

# Linting
poetry run flake8 .
```

### Code Organization

```
aws-v3/
├── aws/
│   ├── core/
│   │   ├── exporters/
│   │   │   ├── {service}/
│   │   │   │   ├── {resource}/
│   │   │   │   │   ├── models.py
│   │   │   │   │   ├── actions.py
│   │   │   │   │   └── exporter.py
│   │   │   │   └── __init__.py
│   │   │   └── ...
│   │   └── ...
│   └── ...
├── tests/
├── main.py
├── integration.py
└── .port/
    └── spec.yaml
```

### Naming Conventions

- **Files**: `snake_case.py`
- **Classes**: `PascalCase`
- **Functions/Variables**: `snake_case`
- **Constants**: `UPPER_SNAKE_CASE`
- **AWS Resources**: `AWS::Service::Resource` (CloudFormation format)

### Documentation Standards

- **Docstrings**: Use Google-style docstrings for all public functions
- **Type Hints**: Include type hints for all function parameters and return values
- **Comments**: Add comments for complex business logic
- **README**: Update relevant README files

### Example Code Structure

```python
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from loguru import logger

class YourResourceProperties(BaseModel):
    """Properties for AWS YourResource."""

    name: str = Field(..., description="Resource name")
    arn: str = Field(..., description="Resource ARN")

    class Config:
        extra = "forbid"
        populate_by_name = True


async def fetch_resource_data(
    client: Any,
    resource_id: str
) -> Dict[str, Any]:
    """Fetch detailed data for a specific resource.

    Args:
        client: AWS client instance
        resource_id: Unique identifier for the resource

    Returns:
        Dictionary containing resource data

    Raises:
        ClientError: If AWS API call fails
    """
    try:
        response = await client.describe_resource(ResourceId=resource_id)
        logger.info(f"Successfully fetched data for resource {resource_id}")
        return response
    except client.exceptions.ClientError as e:
        logger.error(f"Failed to fetch resource {resource_id}: {e}")
        raise
```

## Testing

### Test Structure

```
tests/
├── unit/
│   ├── test_models.py
│   ├── test_actions.py
│   └── test_exporters.py
├── integration/
│   ├── test_aws_resources.py
│   └── test_end_to_end.py
└── fixtures/
    └── aws_responses.json
```

### Writing Tests

#### Unit Tests

```python
import pytest
from unittest.mock import AsyncMock, MagicMock
from aws.core.exporters.sqs.queue.actions import GetQueueAttributesAction

@pytest.mark.asyncio
async def test_get_queue_attributes_success():
    """Test successful queue attributes retrieval."""
    action = GetQueueAttributesAction()
    action.client = AsyncMock()
    action.client.get_queue_attributes.return_value = {
        "Attributes": {
            "QueueName": "test-queue",
            "QueueArn": "arn:aws:sqs:us-east-1:123456789012:test-queue"
        }
    }

    result = await action._execute([{"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"}])

    assert len(result) == 1
    assert result[0]["QueueName"] == "test-queue"
    assert result[0]["QueueArn"] == "arn:aws:sqs:us-east-1:123456789012:test-queue"


@pytest.mark.asyncio
async def test_get_queue_attributes_error_handling():
    """Test error handling in queue attributes retrieval."""
    action = GetQueueAttributesAction()
    action.client = AsyncMock()
    action.client.get_queue_attributes.side_effect = Exception("API Error")

    result = await action._execute([{"QueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/test-queue"}])

    assert len(result) == 0  # Should return empty list on error
```

#### Integration Tests

```python
import pytest
from aws.core.exporters.sqs import SqsQueueExporter
from aws.core.exporters.sqs.queue.models import PaginatedQueueRequest

@pytest.mark.integration
@pytest.mark.asyncio
async def test_sqs_queue_export_real_aws():
    """Test SQS queue export with real AWS resources."""
    # This test requires real AWS credentials and resources
    exporter = SqsQueueExporter(session)
    options = PaginatedQueueRequest(
        region="us-east-1",
        account_id="123456789012"
    )

    resources = []
    async for batch in exporter.get_paginated_resources(options):
        resources.extend(batch)

    assert len(resources) > 0
    assert all(resource["Type"] == "AWS::SQS::Queue" for resource in resources)
```

### Running Tests

```bash
# Run all tests
poetry run pytest

# Run specific test file
poetry run pytest tests/unit/test_actions.py

# Run with coverage
poetry run pytest --cov=aws --cov-report=html

# Run integration tests (requires AWS credentials)
poetry run pytest -m integration

# Run tests in parallel
poetry run pytest -n auto
```

### Test Data

- **Fixtures**: Use pytest fixtures for common test data
- **Mocking**: Mock AWS API calls in unit tests
- **Real Data**: Use real AWS resources for integration tests
- **Edge Cases**: Test error conditions and edge cases

## Pull Request Process

### Before Submitting

1. **Run Tests**: Ensure all tests pass
2. **Code Quality**: Run linting and formatting tools
3. **Documentation**: Update relevant documentation
4. **Changelog**: Add entry to CHANGELOG.md
5. **Self Review**: Review your own code

### PR Template

```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
- [ ] Unit tests added/updated
- [ ] Integration tests added/updated
- [ ] Manual testing completed

## Checklist
- [ ] Code follows style guidelines
- [ ] Self-review completed
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Tests pass
```

### Review Process

1. **Automated Checks**: CI/CD pipeline runs tests and linting
2. **Code Review**: At least one maintainer reviews the code
3. **Testing**: Manual testing may be required for complex changes
4. **Approval**: Maintainer approves and merges the PR

## Release Process

### Versioning

We follow [Semantic Versioning](https://semver.org/):
- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Release Checklist

- [ ] All tests pass
- [ ] Documentation updated
- [ ] Changelog updated
- [ ] Version bumped
- [ ] Release notes prepared
- [ ] Integration tested

## Development Workflow

### Branch Strategy

- **main**: Production-ready code
- **develop**: Integration branch for features
- **feature/**: Feature branches
- **bugfix/**: Bug fix branches
- **hotfix/**: Critical fixes

### Commit Messages

Use conventional commits:

```
feat: add SQS queue support
fix: handle S3 bucket location errors
docs: update contributing guidelines
test: add unit tests for SQS actions
```

### Code Review Guidelines

#### For Contributors

- **Small PRs**: Keep pull requests focused and small
- **Clear Description**: Explain what and why
- **Test Coverage**: Include tests for new functionality
- **Documentation**: Update relevant docs

#### For Reviewers

- **Be Constructive**: Provide helpful feedback
- **Test Thoroughly**: Verify the changes work as expected
- **Check Standards**: Ensure code follows guidelines
- **Consider Impact**: Think about broader implications

## Troubleshooting

### Common Issues

1. **Import Errors**: Check file paths and `__init__.py` files
2. **AWS Permissions**: Ensure credentials have necessary permissions
3. **Test Failures**: Check test data and mocking
4. **Type Errors**: Verify Pydantic models and type hints

### Getting Help

- **GitHub Issues**: Create an issue for bugs or questions
- **Discussions**: Use GitHub Discussions for general questions
- **Documentation**: Check existing documentation first
- **Code Examples**: Look at existing implementations

## Resources

- [ADDING_NEW_KINDS.md](./ADDING_NEW_KINDS.md) - Guide for adding new resource kinds
- [AWS SDK Documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/index.html)
- [Pydantic Documentation](https://pydantic-docs.helpmanual.io/)
- [Ocean Framework Documentation](https://docs.getport.io/ocean/)

## License

By contributing to this project, you agree that your contributions will be licensed under the same license as the project.

---

Thank you for contributing to the AWS-v3 integration! Your contributions help make this integration more powerful and useful for the community.
