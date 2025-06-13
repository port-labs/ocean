---
title: User Agent
sidebar_label: 🕵️‍♂️ User Agent
sidebar_position: 5
description: Access only the relevant data for the integration
---

# 🕵️‍♂️ User Agent

The Ocean framework ingests entities into Port using the [sync entities state](../features/sync.md) functionality. Upon
registering an entity (create/update) Port will mark the integration as its maintainer. This means that the integration
will be able to look up for its own managed entities.

Ocean is using the [`User-Agent`](https://developer.mozilla.org/en-US/docs/Web/HTTP/Headers/User-Agent) header to let Port know which specific integration it is and which specific feature its using to ingest those entities.

:::info Format
Here is the format of the user agent sent to Port:

`port-ocean/<integration_type>/<integration_identifier>/<integration_version>/<feature>`

For example:

`port-ocean/gitlab/my_gitlab_integration/0.1.9/exporter`

or

`port-ocean/github/my_github_integration/0.1.9/gitops`
:::

## Features

The [feature](../../developing-an-integration/defining-configuration-files#features-specification) specified in the user agent header allows Ocean to distinguish between entities created by different features of the same
integration.

For example, if an integration creates entities using both the `exporter` feature and the `gitops` feature,
Ocean will be able to sync each one of them separately without unnecessarily modifying the state of entities managed by the other feature.

By default, Ocean will use the `exporter` feature if no user agent was specified. To specify a user agent, pass the user agent to one of the [Sync Entities State](../features/sync.md) functions.

The following example will sync entities using the `gitops` feature:

```python showLineNumbers
from port_ocean.context.ocean import ocean
# highlight-next-line
from port_ocean.clients.port.types import UserAgentType


@ocean.router.post("/resync_gitops")
def resync_gitops():
    # Note the use of the ocean.sync function rather than raw_sync, see below for an explanation
    await ocean.sync(
        [...],
        # highlight-next-line
        UserAgentType.gitops,
    )
```

:::info
Because the `UserAgentType.gitops` is specified then Ocean will query only the `gitops` related entities managed by the integration.

By default an integration will query entities marked with the `exporter` feature and user agent.

When a different feature is specified using the user agent, the integration performs an entity state sync only for entities managed by the specified feature.
:::

### Available user agent and features

The following features use the user agent header to ingest their own managed entities:

- `exporter` - the exporter feature is used for integrations that perform a simple export and sync of entities from the 3rd-party service into Port (using queries to the 3rd-party API for example). This is the default user agent feature. This feature is used by the [sync entities state](../features/sync.md) functions
  when no user agent was specified
- `gitops` - the GitOps feature is used for integrations that perform an entity sync based on the state of files and entity in a Git provider (by reading the content of specification files for example)

  :::tip
  GitOps is usually used with Ocean sync functionality and not sync raw because of the GitOps format which already contains fully formatted entity objects that do not require an additional transformation is already using the resource mapping.
  :::
