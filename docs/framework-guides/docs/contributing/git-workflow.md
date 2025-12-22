---
title: Git Workflow
sidebar_label: 🔄 Git Workflow
sidebar_position: 6
---

# 🔄 Git Workflow

This guide covers our git workflow, commit message conventions, and pre-commit hooks.

## Workflow Overview

1. **Fork** the Ocean repository
2. **Clone** your fork locally
3. **Create branch** for your changes
4. **Make changes** following our standards
5. **Commit** with clear messages
6. **Push** to your fork
7. **Create PR** to main repository

## Forking and Cloning

### Fork Repository

1. Go to [Ocean repository](https://github.com/port-labs/ocean)
2. Click "Fork" button
3. Select your account

### Clone Your Fork

```bash
git clone https://github.com/your-username/ocean.git
cd ocean
```

### Add Upstream Remote

```bash
git remote add upstream https://github.com/port-labs/ocean.git
```

## Branch Management

### Creating a Branch

```bash
# Update main branch
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/my-feature
```

### Branch Naming

Follow these conventions:

- **Feature**: `feature/description-of-feature`
- **Bug fix**: `fix/description-of-bug`
- **Integration**: `integration/integration-name-feature`
- **Docs**: `docs/description-of-change`

**Examples**:
- `feature/add-retry-mechanism`
- `fix/handle-rate-limit-errors`
- `integration/aws-region-support`
- `docs/update-api-documentation`

### Keeping Branch Updated

```bash
# Fetch latest changes
git fetch upstream

# Rebase your branch on main
git checkout feature/my-feature
git rebase upstream/main
```

## Commit Messages

### Format

```
Type: Brief description (50 chars or less)

Optional detailed description explaining what and why.
Can wrap to multiple lines.
```

### Commit Types

- **`feat`**: New feature
- **`fix`**: Bug fix
- **`docs`**: Documentation changes
- **`refactor`**: Code refactoring
- **`test`**: Test additions/changes
- **`chore`**: Maintenance tasks
- **`style`**: Code style changes (formatting, etc.)
- **`perf`**: Performance improvements

### Examples

```bash
# Feature
git commit -m "feat: Add retry mechanism for API calls

Implements exponential backoff retry logic for handling
rate limit errors and transient failures."

# Bug fix
git commit -m "fix: Handle None values in resource mapping

Prevents crashes when resources have missing fields."

# Documentation
git commit -m "docs: Update API client documentation

Adds examples for common use cases."

# Refactoring
git commit -m "refactor: Extract common pagination logic

Moves pagination handling to shared utility function."

# Test
git commit -m "test: Add tests for resync error handling

Covers edge cases and error recovery scenarios."
```

### Best Practices

1. **Use imperative mood**: "Add feature" not "Added feature"
2. **Keep first line short**: 50 characters or less
3. **Explain why**: Use body to explain reasoning
4. **Reference issues**: `Fixes #123` or `Closes #456`
5. **One logical change per commit**: Don't mix unrelated changes

## Pre-commit Hooks

Pre-commit hooks automatically run checks before commits.

### Installation

Hooks are installed automatically with:

```bash
make install
```

This runs `pre-commit install` to set up git hooks.

### Configured Hooks

1. **`trailing-whitespace`** - Removes trailing whitespace
2. **`end-of-file-fixer`** - Ensures files end with newline
3. **`check-yaml`** - Validates YAML syntax
4. **`check-added-large-files`** - Prevents large file commits
5. **`check-merge-conflict`** - Detects merge conflict markers
6. **`check-executables-have-shebangs`** - Validates shebangs
7. **`check-symlinks`** - Validates symlinks
8. **`detect-aws-credentials`** - Detects AWS credentials (with `--allow-missing-credentials`)
9. **`fix lint`** - Runs `make lint/fix` on Python files

### Running Hooks Manually

```bash
# Run on all files
pre-commit run --all-files

# Run on staged files only
pre-commit run

# Run specific hook
pre-commit run trailing-whitespace
```

### Bypassing Hooks

⚠️ **Not recommended**, but if needed:

```bash
# Skip hooks for one commit
git commit --no-verify -m "message"
```

## Workflow Steps

### 1. Start Working on Feature

```bash
# Update main
git checkout main
git pull upstream main

# Create feature branch
git checkout -b feature/my-feature
```

### 2. Make Changes

```bash
# Edit files
vim path/to/file.py

# Stage changes
git add path/to/file.py

# Pre-commit hooks run automatically
# Fix any issues, then commit
git commit -m "feat: Add new feature"
```

### 3. Keep Branch Updated

```bash
# Fetch latest
git fetch upstream

# Rebase on main
git rebase upstream/main

# Resolve conflicts if any
# Then continue
git rebase --continue
```

### 4. Push Changes

```bash
# Push to your fork
git push origin feature/my-feature

# If rebased, force push (carefully!)
git push --force-with-lease origin feature/my-feature
```

### 5. Create Pull Request

1. Go to GitHub
2. Click "New Pull Request"
3. Select your branch
4. Fill out PR template
5. Submit PR

## Handling Merge Conflicts

### During Rebase

```bash
# Start rebase
git rebase upstream/main

# If conflicts occur:
# 1. Edit conflicted files
# 2. Stage resolved files
git add path/to/resolved/file.py

# 3. Continue rebase
git rebase --continue

# Or abort if needed
git rebase --abort
```

### Resolving Conflicts

1. **Identify conflicts**: Git marks conflicts with `<<<<<<<`, `=======`, `>>>>>>>`
2. **Edit files**: Remove markers, keep desired code
3. **Stage files**: `git add path/to/file.py`
4. **Continue**: `git rebase --continue`

## Commit History

### Viewing History

```bash
# View commits
git log

# View with details
git log --oneline --graph --decorate

# View specific file history
git log path/to/file.py
```

### Amending Commits

```bash
# Amend last commit
git commit --amend -m "New message"

# Add changes to last commit
git add forgotten-file.py
git commit --amend --no-edit
```

### Squashing Commits

```bash
# Interactive rebase (last 3 commits)
git rebase -i HEAD~3

# In editor, change 'pick' to 'squash' for commits to squash
# Save and close
# Edit commit message
# Save and close
```

## Pull Request Workflow

### Before Creating PR

1. **Ensure tests pass**: `make test`
2. **Ensure linting passes**: `make lint`
3. **Update changelog**: Create towncrier fragment
4. **Bump version**: If needed
5. **Rebase on main**: `git rebase upstream/main`

### Creating PR

1. **Push branch**: `git push origin feature/my-feature`
2. **Go to GitHub**: Navigate to repository
3. **Click "New Pull Request"**
4. **Fill template**: Complete all relevant sections
5. **Submit**: Create PR

### After PR Creation

1. **Monitor CI**: Ensure all checks pass
2. **Address reviews**: Make requested changes
3. **Push updates**: `git push origin feature/my-feature`
4. **Re-request review**: If needed

## Best Practices

### 1. Small, Focused Commits

```bash
# ✅ Good: Separate commits for different changes
git commit -m "feat: Add retry mechanism"
git commit -m "test: Add tests for retry mechanism"
git commit -m "docs: Update retry documentation"

# ❌ Bad: One commit with everything
git commit -m "Add retry mechanism, tests, and docs"
```

### 2. Commit Often

Commit logical units of work frequently:

```bash
# After completing a feature
git add feature.py
git commit -m "feat: Implement feature X"

# After adding tests
git add test_feature.py
git commit -m "test: Add tests for feature X"
```

### 3. Write Clear Messages

```bash
# ✅ Good
git commit -m "fix: Handle None values in resource mapping

Prevents crashes when resources have missing optional fields.
Adds validation to ensure required fields are present."

# ❌ Bad
git commit -m "fix stuff"
```

### 4. Review Before Committing

```bash
# See what will be committed
git status
git diff --staged

# Review changes
git diff
```

### 5. Keep Main Clean

Never commit directly to main:

```bash
# ✅ Good: Always use feature branch
git checkout -b feature/my-feature
# ... make changes ...
git commit -m "feat: Add feature"

# ❌ Bad: Committing to main
git checkout main
git commit -m "feat: Add feature"  # Don't do this!
```

## Troubleshooting

### Undo Last Commit (Keep Changes)

```bash
git reset --soft HEAD~1
```

### Undo Last Commit (Discard Changes)

```bash
git reset --hard HEAD~1
```

### Change Last Commit Message

```bash
git commit --amend -m "New message"
```

### Unstage Files

```bash
git reset HEAD path/to/file.py
```

### Discard Local Changes

```bash
git checkout -- path/to/file.py
```

## Resources

- [Git Documentation](https://git-scm.com/doc)
- [GitHub Flow Guide](https://guides.github.com/introduction/flow/)
- [Conventional Commits](https://www.conventionalcommits.org/)
