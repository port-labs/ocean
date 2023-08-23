---
title: User Agent
sidebar_label: 🕵️‍♂️ User Agent
sidebar_position: 5
description: Access only the relevant data for the integration
---

# 🕵️‍♂️ User Agent

The Ocean framework ingest entities into Port using the [Sync Entities State](../features/sync.md) functionality, upon
registering an entity (create/update) Port will mark the integration as its creator. This means that the integration
will be able to look up for its own entities.

Ocean is using the `USER_AGENT` header to let port know which specific integration it is and which specific feature its
using to ingest those entities.

:::info Format
The user agent sent to port is formatted as follows:

`port-ocean/<integration_type>/<integration_identifier>/<integration_version>/<feature>`

For example:

`port-ocean/gitlab/my_gitlab_integration/0.1.9/exporter`

or

`port-ocean/github/my_github_integration/0.1.9/gitops`
:::

## Features

Thea feature in the user agent lets Ocean to distinguish between entities created by different features of the same
integration. For example, if an integration is created entities using the `exporter` feature and the `gitops` feature,
Ocean will be able to sync each one of them separately without touching the other feature entities.

By default, Ocean will use the `exporter` feature if no user agent was specified. To specify a user agent, use the
pass the user agent to one ot the [Sync Entities State](../features/sync.md) functions.

The following example will sync entities using the `gitops` feature:

:::info
Because the `UserAgentType.gitops` is specified then Ocean will query only the `gitops` related entities for this
integration
instead of querying the `exporter` related entities by default and compare the difference between the given entities and
the requested entities that are in Port
:::

```python
from port_ocean.context.ocean import ocean
from port_ocean.clients.port.types import UserAgentType


@ocean.router.post("/resync_gitops")
def resync_gitops():
    await ocean.sync(
        [...],
        UserAgentType.gitops,
    )
```

### Available User Agent Features

The following features are ingesting entities using the User Agent:

- `exporter`
  The default user agent feature. This feature is used by the [Sync Entities State](../features/sync.md) functions
  when no user agent was specified. Used to export entities from the 3rd party application to Port.

- `gitops`
  This feature user agent is used by git integrations like the Gitlab integration to export entities from the git
  project to Port that are specified in a different format than the default `exporter` feature.

  :::note
  Gitops is usually used with Ocean Sync functionality and not Sync Raw because of the gitops format which is already
  constructed in the Port entities format and there is no need top transform its data using the Resource Mapping.
  :::
