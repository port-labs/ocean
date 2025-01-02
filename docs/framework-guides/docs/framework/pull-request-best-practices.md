---
title: Pull Request Best Practices
sidebar_label: 📝 Pull Request Best Practices
sidebar_position: 4
---

# 📝 Pull Request Best Practices

This guide outlines the best practices for creating and managing pull requests in the Ocean framework repository. Following these guidelines helps maintain code quality and ensures smooth collaboration.

## Pull Request Title Format

Pull request titles must follow this pattern:
```
[Category][Optional Subcategory] Description
```

Where:
- `Category` must be one of:
  - `Integration` - Changes to integration code
  - `Core` - Changes to Ocean framework core
  - `Docs` - Documentation changes
  - `CI` - CI/CD pipeline changes
  - `Infra` - Infrastructure changes
- `Optional Subcategory` - Additional context (e.g., `[AWS]`, `[Jira]`)
- `Description` - Clear, concise description of changes

Examples:
- `[Integration][AWS] Add support for ECS tags`
- `[Core] Improve error handling in HTTP client`
- `[Docs] Add Jira integration walkthrough`

## Branch Naming Convention

Branch names should be descriptive and follow this format:
```
feature/short-description
bugfix/issue-description
docs/documentation-change
```

## Pull Request Description

Your PR description should include:

1. **Overview**
   - Brief description of changes
   - Motivation for changes
   - Related issues or discussions

2. **Changes Made**
   - List of significant changes
   - Any breaking changes
   - New features or improvements

3. **Testing**
   - How changes were tested
   - Test coverage information
   - Manual testing steps if applicable

4. **Additional Context**
   - Screenshots (if applicable)
   - Performance implications
   - Security considerations

## Code Review Process

### As a PR Author

1. **Before Creating PR**
   - Run linting checks (`make lint`)
   - Ensure all tests pass
   - Review your own changes
   - Update documentation if needed

2. **After Creating PR**
   - Respond to reviewer comments promptly
   - Make requested changes
   - Keep PR updated with base branch

3. **Before Merging**
   - Ensure CI checks pass
   - Get required approvals
   - Resolve all conversations

### As a Reviewer

1. **Review Checklist**
   - Code follows style guidelines
   - Tests are adequate
   - Documentation is updated
   - Changes meet requirements

2. **Providing Feedback**
   - Be constructive and specific
   - Explain reasoning for changes
   - Distinguish between required and optional changes

## Best Practices

1. **Keep PRs Focused**
   - One feature/fix per PR
   - Limit scope of changes
   - Split large changes into smaller PRs

2. **Commit Messages**
   - Use clear, descriptive messages
   - Reference issues when applicable
   - Follow conventional commits format

3. **Documentation**
   - Update relevant docs
   - Include code comments
   - Add examples for new features

4. **Testing**
   - Add/update tests
   - Test edge cases
   - Include integration tests

5. **Security**
   - No sensitive data in code
   - Follow security best practices
   - Review access controls

## Common Issues to Avoid

1. **Code Quality**
   - Mixing formatting with content changes
   - Large, unfocused PRs
   - Missing tests or documentation

2. **Process**
   - Force pushing to branches
   - Merging without reviews
   - Ignoring CI failures

3. **Communication**
   - Unclear PR descriptions
   - Delayed responses to feedback
   - Missing context or motivation

## Additional Resources

- [Ocean Framework Documentation](./framework.md)
- [Contributing Guidelines](../contributing/contributing.md)
