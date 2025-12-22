---
title: Version Management
sidebar_label: 📌 Version Management
sidebar_position: 5
---

# 📌 Version Management

This guide covers how to manage versions, create changelogs, and use Towncrier for Ocean integrations.

## Overview

Ocean uses **Towncrier** for managing changelogs and **Poetry** for version management. All version changes must include changelog entries.

## Version Bumping

### Single Integration

Bump version for a single integration:

```bash
make bump/single-integration INTEGRATION=aws
```

This will:
1. Show current version
2. Bump patch version automatically (or use `-v` for explicit version)
3. Create towncrier changelog fragments
4. Build changelog
5. Commit changes

**With explicit version**:
```bash
./scripts/bump-single-integration.sh -i aws -v 1.2.3
```

### All Integrations (Ocean Version Update)

Bump Ocean version for all integrations:

```bash
make bump/integrations VERSION=0.32.4
```

This will:
1. Update Ocean dependency version in all integrations
2. Create improvement changelog entry
3. Bump patch version for each integration
4. Commit changes for each integration

## Version Numbering

### Semantic Versioning

Follow [Semantic Versioning](https://semver.org/):

- **MAJOR**: Breaking changes
- **MINOR**: New features (backward compatible)
- **PATCH**: Bug fixes (backward compatible)

### Examples

- `1.0.0` → `1.0.1` (patch bump)
- `1.0.0` → `1.1.0` (minor bump)
- `1.0.0` → `2.0.0` (major bump)

### Beta Versions

For new integrations, start with beta:

- `0.1.0-beta`
- `0.1.0-beta.1` (if multiple beta releases)

## Towncrier

Towncrier manages changelog entries through news fragments.

### Changelog Types

Available types (in `pyproject.toml`):

1. **`breaking`** - Breaking Changes
2. **`deprecation`** - Deprecations
3. **`feature`** - Features
4. **`improvement`** - Improvements
5. **`bugfix`** - Bug Fixes
6. **`doc`** - Improved Documentation

### Creating Changelog Fragments

#### Manual Creation

Create a file in `changelog/` directory:

```bash
# Format: {issue_number}.{type}.md
# Example:
changelog/123.feature.md
```

Content:
```markdown
Added support for region-specific resource querying in AWS integration.
```

#### Using Towncrier CLI

```bash
poetry run towncrier create --content "Your changelog message" +random.{type}.md
```

**Examples**:
```bash
# Feature
poetry run towncrier create --content "Add retry mechanism" +random.feature.md

# Bug fix
poetry run towncrier create --content "Fix rate limit handling" +random.bugfix.md

# Breaking change
poetry run towncrier create --content "Refactor API client interface" +random.breaking.md
```

### Building Changelog

After creating fragments, build the changelog:

```bash
poetry run towncrier build --yes --version 1.2.3
```

This will:
1. Collect all fragments
2. Generate changelog entries
3. Update `CHANGELOG.md`
4. Remove fragment files (unless `--keep` is used)

### Fragment File Format

**Location**: `changelog/{issue_number}.{type}.md`

**Content**: Plain text description

**Example** (`changelog/456.feature.md`):
```markdown
Added support for multi-region resource syncing in AWS integration.
```

## Version Bumping Workflow

### For New Features

1. **Create changelog fragment**:
   ```bash
   poetry run towncrier create --content "Add new feature" +random.feature.md
   ```

2. **Bump version**:
   ```bash
   make bump/single-integration INTEGRATION=my-integration
   ```
   Or manually:
   ```bash
   poetry version patch  # or minor, major
   ```

3. **Build changelog**:
   ```bash
   poetry run towncrier build --yes --version $(poetry version --short)
   ```

4. **Commit changes**:
   ```bash
   git add pyproject.toml CHANGELOG.md changelog/
   git commit -m "Bump version and update changelog"
   ```

### For Bug Fixes

1. **Create bugfix fragment**:
   ```bash
   poetry run towncrier create --content "Fix issue description" +random.bugfix.md
   ```

2. **Bump patch version**:
   ```bash
   poetry version patch
   ```

3. **Build changelog**:
   ```bash
   poetry run towncrier build --yes --version $(poetry version --short)
   ```

### For Breaking Changes

1. **Create breaking fragment**:
   ```bash
   poetry run towncrier create --content "Breaking: Description" +random.breaking.md
   ```

2. **Bump major version**:
   ```bash
   poetry version major
   ```

3. **Build changelog**:
   ```bash
   poetry run towncrier build --yes --version $(poetry version --short)
   ```

## Changelog Format

Generated changelog follows this format:

```markdown
## 1.2.3 (2024-01-15)

### Features
- Added support for region-specific resource querying

### Bug Fixes
- Fixed rate limit handling in API client

### Improvements
- Improved error messages for authentication failures
```

## Integration Version Bumping Script

The `bump-single-integration.sh` script automates the process:

```bash
./scripts/bump-single-integration.sh -i integration-name -v 1.2.3
```

**What it does**:
1. Validates integration exists
2. Shows current version
3. Bumps version (patch by default, or explicit with `-v`)
4. Prompts for changelog fragments (interactive)
5. Builds changelog
6. Commits changes

**Interactive mode**:
- Prompts for changelog type for each commit
- Uses `fzf` if available, otherwise menu selection
- Creates fragments automatically

## Ocean Core Version Updates

When Ocean core is updated, all integrations need to update their dependency:

```bash
make bump/integrations VERSION=0.32.4
```

**What it does**:
1. Updates `port-ocean` dependency in each integration
2. Creates improvement changelog entry
3. Bumps patch version
4. Commits changes

**Automated**: This is often done via GitHub Actions when Ocean core is released.

## Version in pyproject.toml

Version is stored in `pyproject.toml`:

```toml
[tool.poetry]
version = "1.2.3"
```

**Update manually**:
```bash
poetry version 1.2.3
poetry version patch   # Bumps patch
poetry version minor   # Bumps minor
poetry version major   # Bumps major
```

**Check current version**:
```bash
poetry version --short
```

## Best Practices

### 1. Always Create Changelog Entries

Every version bump should include changelog entries:

```bash
# Create fragment first
poetry run towncrier create --content "Description" +random.feature.md

# Then bump version
poetry version patch

# Build changelog
poetry run towncrier build --yes --version $(poetry version --short)
```

### 2. Use Appropriate Changelog Types

- **`feature`**: New functionality
- **`bugfix`**: Bug fixes
- **`improvement`**: Enhancements to existing features
- **`breaking`**: Breaking changes
- **`deprecation`**: Deprecated features
- **`doc`**: Documentation updates

### 3. Write Clear Changelog Messages

```markdown
# ✅ Good
Added support for multi-region resource syncing in AWS integration.

# ❌ Bad
Fixed stuff
```

### 4. One Entry Per Change

Create separate fragments for different changes:

```bash
# Multiple fragments
changelog/123.feature.md
changelog/124.bugfix.md
changelog/125.improvement.md
```

### 5. Remove Fragments After Building

Towncrier removes fragments by default. If you use `--keep`, remember to clean up:

```bash
rm changelog/*.md
```

## Troubleshooting

### Fragment Not Included

**Issue**: Fragment not appearing in changelog

**Solution**:
1. Check file name format: `{number}.{type}.md`
2. Verify type is valid: `breaking`, `deprecation`, `feature`, `improvement`, `bugfix`, `doc`
3. Ensure file is in `changelog/` directory
4. Run `towncrier build` again

### Version Already Exists

**Issue**: Towncrier complains about existing version

**Solution**:
```bash
# Use --version to specify new version
poetry run towncrier build --yes --version 1.2.4
```

### Multiple Fragments for Same Issue

**Issue**: Multiple fragments with same issue number

**Solution**: Towncrier will combine them. Use different issue numbers or combine content.

## Resources

- [Towncrier Documentation](https://towncrier.readthedocs.io/)
- [Semantic Versioning](https://semver.org/)
- [Poetry Version Command](https://python-poetry.org/docs/cli/#version)
