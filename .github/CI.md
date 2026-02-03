# CI/CD Workflows

This document describes the CI/CD workflows in this repository.

## Core Test Workflow (`core-test.yml`)

Runs when core code changes (port_ocean library or CI files).

### Jobs

| Job | Purpose |
|-----|---------|
| detect-changes | Determines what changed to decide which tests to run |
| core-unit-tests | Runs unit tests on the ocean core library, builds tarball |
| smoke-tests | End-to-end tests with fake integration (single + multi process modes) |
| test-integrations | Runs all integration test suites against the current core |
| aggregate-coverage | Merges coverage reports and posts to PR |

### Job Dependencies

```
detect-changes ──┬──> core-unit-tests ──┬──> smoke-tests ────────┬──> aggregate-coverage
                 │                      └──> test-integrations ──┘
                 └────────────────────────────────────────────────┘
```

### Smart Caching

Integration venvs are cached using a hash that excludes the `port-ocean` package.
This prevents cache invalidation when only the core version is bumped (since
core is installed from the locally-built tarball anyway).

See: `scripts/get-deps-hash.sh`

## Other Workflows

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| lint.yml | PR, push to main | Runs linting on changed files |
| integrations-test.yml | PR (integration changes) | Tests individual integrations |
| release-framework.yml | Tag push | Releases the ocean framework |
| release-integrations.yml | Tag push | Releases integrations |
