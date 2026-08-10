---
title: Contributing
---

# 🤝 Contributing

import TBD from '../\_common/tbd.md';

## Report a Bug

<TBD />

## Suggest a Feature

<TBD />

## Develop a New Feature

<TBD />

### Releasing changes

When contributing changes to an integration under `integrations/` or the Ocean framework under
`port_ocean/`, declare how the change should be released using one of the following options.

#### Option A — declarative release (recommended)

Add a release intent file (changeset) alongside your code changes:

- Integration: `integrations/<name>/.ocean-release/<unique-name>.yaml`
- Ocean core: `.ocean-release/core/<unique-name>.yaml`

```yaml
bump: patch
changelog-type: bugfix
changelog: Describe the change
```

`bump` must be one of `patch`, `minor`, or `major`. `changelog-type` must be one of `breaking`,
`deprecation`, `feature`, `improvement`, `bugfix`, or `doc`.

After your PR is merged to `main`, CI opens a follow-up PR with the version bump and changelog
updates. Review and merge that PR to publish the release.

#### Option B — manual release

Bump the version in `pyproject.toml` and add an entry to `CHANGELOG.md`. If you update both manually
and add a release intent file, the manual changes take priority.

For the full publishing workflow, see [Publishing Your Integration](../developing-an-integration/publishing-your-integration.md).

## Suggest a Documentation Change

<TBD />
