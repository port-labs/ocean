---
title: PR Process
sidebar_label: 🔀 PR Process
sidebar_position: 4
---

# 🔀 PR Process

This guide covers how to create pull requests, branch naming conventions, PR requirements, and the review process.

## PR Title Format

**All PR titles must follow this format** (enforced by CI):

```
[Type] Description
```

### Types

- `[Integration]` - Changes to integrations
- `[Core]` - Changes to Ocean framework/core
- `[Docs]` - Documentation changes
- `[CI]` - CI/CD changes
- `[Infra]` - Infrastructure changes

### Optional Tags

You can add optional tags in square brackets:

```
[Integration][AWS] Enable region-specific resource querying support
[Core][Breaking] Refactor event listener interface
```

### Examples

✅ **Valid PR titles**:
- `[Integration] Resolve missing team context in board ingestion for non-default teams`
- `[Core] Ensure ingestion of integration logs`
- `[Core] Upgrade FastAPI version to improve performance and compatibility`
- `[Docs] Correct documentation on Ocean's denial-of-service vulnerability`
- `[Integration] Enable region-specific resource querying support`

❌ **Invalid PR titles**:
- `Fix bug` (missing type)
- `integration: add feature` (wrong format)
- `[Feature] Add new integration` (wrong type, should be `[Integration]`)

## Branch Naming

While not strictly enforced, follow these conventions:

### Recommended Patterns

- **Feature**: `feature/description-of-feature`
- **Bug fix**: `fix/description-of-bug`
- **Integration**: `integration/integration-name-feature`
- **Docs**: `docs/description-of-change`

### Examples

- `feature/add-retry-mechanism`
- `fix/handle-rate-limit-errors`
- `integration/aws-region-support`
- `docs/update-api-documentation`

### Automated Branches

Some branches are created automatically:
- `apply-ocean-{version}-to-all-integrations` - Created by CI for version bumps
- `combine-prs-branch` - Created for combining multiple PRs

## PR Template

When creating a PR, fill out the template:

### Description Section

```markdown
What - Brief description of what changed
Why - Reason for the change
How - How the change was implemented
```

### Type of Change

Select one:
- [ ] Bug fix (non-breaking change which fixes an issue)
- [ ] New feature (non-breaking change which adds functionality)
- [ ] New Integration (non-breaking change which adds a new integration)
- [ ] Breaking change (fix or feature that would cause existing functionality to not work as expected)
- [ ] Non-breaking change (fix of existing functionality that will not change current behavior)
- [ ] Documentation (added/updated documentation)

### Testing Checklist

#### Core Testing Checklist

For Ocean core changes:

- [ ] Integration able to create all default resources from scratch
- [ ] Resync finishes successfully
- [ ] Resync able to create entities
- [ ] Resync able to update entities
- [ ] Resync able to detect and delete entities
- [ ] Scheduled resync able to abort existing resync and start a new one
- [ ] Tested with at least 2 integrations from scratch
- [ ] Tested with Kafka and Polling event listeners
- [ ] Tested deletion of entities that don't pass the selector

#### Integration Testing Checklist

For integration changes:

- [ ] Integration able to create all default resources from scratch
- [ ] Completed a full resync from a freshly installed integration and it completed successfully
- [ ] Resync able to create entities
- [ ] Resync able to update entities
- [ ] Resync able to detect and delete entities
- [ ] Resync finishes successfully
- [ ] If new resource kind is added or updated, add example raw data, mapping and expected result to the `examples` folder
- [ ] If resource kind is updated, run the integration with the example data and check if the expected result is achieved
- [ ] If new resource kind is added or updated, validate that live-events for that resource are working as expected
- [ ] Docs PR link [here](#)

#### Preflight Checklist

- [ ] Handled rate limiting
- [ ] Handled pagination
- [ ] Implemented the code in async
- [ ] Support Multi account (if applicable)

### Additional Sections

- **Screenshots**: Include screenshots showing how resources look
- **API Documentation**: Provide links to API documentation used

## PR Requirements

### Before Submitting

1. **Run linting**: `make lint` must pass
2. **Run tests**: `make test` must pass
3. **Update changelog**: Create towncrier fragment (see [Version Management](./version-management.md))
4. **Update version**: Bump version if needed (see [Version Management](./version-management.md))
5. **Fill PR template**: Complete all relevant sections

### CI Checks

Your PR must pass:

1. **Linting**: `make lint` (black, ruff, mypy, yamllint)
2. **PR Title**: Must match format `[Type] Description`
3. **Tests**: Unit and integration tests
4. **Integration-specific checks**: If changing integrations

### Testing Requirements

⚠️ **Important**: All tests should be run against Port production environment (using a testing org).

## PR Review Process

### What Reviewers Look For

1. **Code Quality**
   - Follows code style guidelines
   - Proper error handling
   - Type hints where appropriate
   - Clear and readable code

2. **Testing**
   - Adequate test coverage
   - Tests pass locally and in CI
   - Edge cases covered

3. **Functionality**
   - Works as described
   - Handles errors gracefully
   - Performance considerations

4. **Documentation**
   - Code is well-documented
   - PR description is clear
   - Changelog updated

### Review Checklist

Before requesting review, ensure:

- [ ] All CI checks pass
- [ ] PR template filled out
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Changelog created
- [ ] Version bumped (if needed)
- [ ] No merge conflicts

### Getting Approval

- **Required**: Sign-off from at least one Port developer
- **Process**: Address review comments, push changes, re-request review
- **Merge**: Once approved, maintainers will merge

## Commit Messages

While not strictly enforced, follow these guidelines:

### Format

```
Type: Brief description

Optional detailed description explaining what and why.
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation
- `refactor`: Code refactoring
- `test`: Tests
- `chore`: Maintenance

### Examples

```
feat: Add retry mechanism for API calls

Implements exponential backoff retry logic for handling
rate limit errors and transient failures.

fix: Handle None values in resource mapping

Prevents crashes when resources have missing fields.

docs: Update API client documentation

Adds examples for common use cases.
```

## PR Size Guidelines

- **Small PRs preferred**: Easier to review and merge
- **Large changes**: Consider breaking into multiple PRs
- **Related changes**: Group logically related changes together

## Addressing Review Comments

1. **Acknowledge**: Comment on the review
2. **Make changes**: Update code as requested
3. **Push changes**: Commit and push updates
4. **Re-request review**: Ask for another review if needed

## Merging

- **Who merges**: Port maintainers merge PRs
- **When**: After approval and all checks pass
- **How**: Typically squash merge or merge commit

## Common PR Issues

### CI Failures

1. **Linting errors**: Run `make lint/fix`
2. **Test failures**: Fix failing tests locally first
3. **Type errors**: Add type hints or use `type: ignore` sparingly

### Merge Conflicts

1. **Rebase**: `git rebase main`
2. **Resolve conflicts**: Edit conflicted files
3. **Continue**: `git rebase --continue`
4. **Force push**: `git push --force-with-lease`

### PR Title Validation

If PR title validation fails:
1. Check format: `[Type] Description`
2. Use valid type: `Integration`, `Core`, `Docs`, `CI`, `Infra`
3. Update title in PR settings

## Resources

- [GitHub Pull Request Guide](https://docs.github.com/en/pull-requests)
- [Code Review Best Practices](https://github.com/google/eng-practices/blob/master/review/)
