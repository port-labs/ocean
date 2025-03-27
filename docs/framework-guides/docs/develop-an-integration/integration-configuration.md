---
title: Integration Configuration
sidebar_label: 🏗️ Integration Configuration
sidebar_position: 3
---

import EventListenerTypesList from '../framework/features/\_event-listener-types-list.md'
import ResyncAbortMessage from '@site/docs/_common/resync-abort-message.mdx';

# 🏗️ Integration Configuration

This section explains the structure of the `config.yaml` file.

## `config.yaml` file

The `config.yaml` file is used to specify the default configuration and parameters for the integration during its deployment phase.

When an integration is first started, it registers itself with [Port's REST API](https://api.getport.io/static/index.html#/Integrations/post_v1_integration), using the `https://api.getport.io/v1/integration` route.

During this first boot registration, it uses the configuration specified in the `config.yaml` file for its default inputs and parameters (unless those are overridden by the environment variables of the running environment/shell)

### Structure

Here is a brand new `config.yaml` file created as part of the `ocean new` command:

```yaml showLineNumbers
# This is an example configuration file for the integration service.
# Please copy this file to config.yaml file in the integration folder and edit it to your needs.
initializePortResources: true
scheduledResyncInterval: 1440 # 60 minutes X 24 hours = 1 day
port:
  clientId: "{{ from env PORT_CLIENT_ID }}" # Can be loaded using environment variable: PORT_CLIENT_ID
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}" # Can be loaded using environment variable: PORT_CLIENT_SECRET
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
    someApplicationUrl: "https://example.com"
```

Let's go over the different sections and their allowed values:

#### `initializePortResources` - Initialize Port resources

This configuration is used to specify whether the integration should initialize its default resources in Port as 
described in the [integration specification](./integration-spec-and-default-resources.md#default-resources).

By default, this feature value is set to `false`. To enable it, set the value to `true`.

```yaml showLineNumbers
initializePortResources: true
```

#### `scheduledResyncInterval` - Run scheduled resync

This configuration is used to specify the interval in minutes in which the integration should initiate a full resync from the 3rd-party system.

By default, this feature is disabled in most integrations. To enable it, set the value to a positive integer representing the interval in
minutes.

<ResyncAbortMessage />

:::note
Unlike the [Polling](../framework/features/event-listener.md#polling) event listener, this configuration will start the resync regardless of
whether there are any changes in the [Port App Config](./trigger-your-integration.md).
:::

```yaml showLineNumbers
scheduledResyncInterval: 1440 # 60 minutes X 24 hours = 1 day
```

#### `port` - Port API credentials

```yaml showLineNumbers
port:
  clientId: "{{ from env PORT_CLIENT_ID }}" # Can be loaded using environment variable: PORT_CLIENT_ID
  clientSecret: "{{ from env PORT_CLIENT_SECRET }}" # Can be loaded using environment variable: PORT_CLIENT_SECRET
```

This section is used to provide the integration with [credentials](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/api/#find-your-port-credentials) to Port's API.

The required parameters are the Port client ID and client secret. As seen in the default configuration, these parameters are taken from the environment variables of the environment running the integration:

- Port client ID - taken from the `PORT_CLIENT_ID` environment variable
- Port client secret - taken from the `PORT_CLIENT_SECRET` environment variable

For local development, it is possible to export the client ID and secret as environment variables to your shell with the following commands:

```bash showLineNumbers
export PORT_CLIENT_ID="<YOUR_CLIENT_ID>"
export PORT_CLIENT_SECRET="<YOUR_CLIENT_SECRET>"
```

It is also possible to replace the environment variables import syntax (`"{{ from env PORT_CLIENT_ID }}"`) with the real value of your Port client ID and secret:

```yaml showLineNumbers
port:
  clientId: "<YOUR_CLIENT_ID>"
  clientSecret: "<YOUR_CLIENT_SECRET>"
```

:::warning
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

To learn more about a specific event listener, click on its name in the list.

#### `integration` - configure the integration object in Port

```yaml showLineNumbers
integration:
  # The identifier of this integration instance.
  identifier: "{{ from env INTEGRATION_IDENTIFIER }}"
  # The type of the integration.
  type: "My Integration type (Gitlab, Jira, etc.)"
  config: ...
```

This section is used to specify the integration type (for display in Port) and the integration identifier to uniquely identify the integration in case a user has multiple deployments of an integration of the same type.

The required parameters are the integration `type` (this field should match the `type` specified in the [integration specification](./integration-spec-and-default-resources.md#specyaml-file)) and the integration `identifier`. In addition to those, an integration can define as many additional parameters and inputs under the `config` object:

##### `config` - integration inputs and parameters

```yaml showLineNumbers
integration:
  config:
    myGitToken: "{{ from env MY_GIT_TOKEN }}"
    someApplicationUrl: "https://example.com"
```

This section is used to specify the inputs and parameters required by the integration, an integration can use any number of required parameters and inputs. Inputs can either be static hard-coded values, or dynamic values taken from the environment variables of the running environment/shell.

As the integration developer, you can use the `config` object to receive as many inputs from the user as you require for the integration's proper operation, some common example inputs for the `config` object:

- Secret tokens and credentials to access 3rd-party services
- URLs to APIs the integration will send requests to that are not static. For example, the Ocean integration for Jira receives a `jiraHost` parameter that specifies the URL of the user's Jira, for example: https://example.atlassian.net
- Parameters used to configure the integration behavior. For example, a `pageSize` parameter to specify the amount of entries queried from a 3rd-party service when performing a data resync
- etc
