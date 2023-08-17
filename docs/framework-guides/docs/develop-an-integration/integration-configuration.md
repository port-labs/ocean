---
title: 🏗️ Integration Configuration
sidebar_position: 3
---

import EventListenerTypesList from '../framework/features/\_event-listener-types-list.md'

# 🏗️ Integration Configuration

This section explains the structure of the `config.yml` file.

## `config.yaml` file

The `config.yaml` file is used to specify the default configuration and parameters for the integration during its deployment phase.

When an integration is first started, it registers itself with Port's REST API, via the `https://api.getport.io/v1/integration` route.

During this first boot registration, it uses the configuration specified in the `config.yaml` file for its default inputs and parameters (unless those are overridden by the environment variables of the running environment/shell)

### Structure

Here is a brand new `config.yaml` file created as part of the `ocean new` command:

```yaml showLineNumbers
# This is an example configuration file for the integration service.
# Please copy this file to config.yaml file in the integration folder and edit it to your needs.

port:
  clientId: "{{ from env PORT_CLIENT_ID }}" # Can be loaded via environment variable: PORT_CLIENT_ID
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}" # Can be loaded via environment variable: PORT_CLIENT_SECRET
# The event listener to use for the integration service.
eventListener:
  type: KAFKA
integration:
  # The identifier of this integration instance.
  identifier: "{{ from env INTEGRATION_IDENTIFIER }}"
  # The type of the integration.
  type: "My Integration type (Gitlab, Jira, etc.)"
  config:
    myGitToken: "{{ from env MY_GIT_TOKEN }}"
    someApplicationUrl: "https://I-Am-Not-A-Real-Url.com"
```

Let's go over the different sections and their allowed values:

#### `port` - Port API credentials

```yaml showLineNumbers
port:
  clientId: "{{ from env PORT_CLIENT_ID }}" # Can be loaded via environment variable: PORT_CLIENT_ID
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}" # Can be loaded via environment variable: PORT_CLIENT_SECRET
```

This section is used to provide the integration with [credentials](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/api/#find-your-port-credentials) to Port's API.

The required parameters are the Port client ID and client secret. As seen in the default configuration, these parameters are taken from the environment variables of the environment running the integration:

- Port client ID - taken from the `PORT_CLIENT_ID` environment variable
- Port client secret - taken from the `PORT_CLIENT_SECRET` environment variable

For local development, it is possible to export the client ID and secret as environment variables to your shell with the following commands:

```shell showLineNumbers
export PORT_CLIENT_ID="<YOUR_CLIENT_ID>"
export PORT_CLIENT_SECRET="<YOUR_CLIENT_SECRET>"
```

It is also possible to replace the environment variables import syntax (`"{{ from env PORT_CLIENT_ID }}"`) with the real value of your Port client ID and secret:

```yaml showLineNumbers
port:
  clientId: "<YOUR_CLIENT_ID>"
  clientSecret: "<YOUR_CLIENT_SECRET>"
```

:::caution
Remember that your Port client ID and secret are API credentials which are sensitive and whose values should not be committed to git
:::

:::note
In case you directly write the client ID and secret in the `port` section, when publishing the integration the values in this section need to be **returned to their defaults** so that they properly read the credentials from the environment variables
:::

#### `eventListener` - how to trigger & resync an integration

```yaml showLineNumbers
# The event listener to use for the integration service.
eventListener:
  type: KAFKA
```

This section is used to specify the type of event listener the integration will use to receive events and resync requests from Port.

<EventListenerTypesList/>
