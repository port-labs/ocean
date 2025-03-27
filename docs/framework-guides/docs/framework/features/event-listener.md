---
title: Event Listener
sidebar_label: 🔈 Event Listener
sidebar_position: 3
description: Use event listeners to receive configurations from Port
---

import EventListenerTypesList from './\_event-listener-types-list.md';
import ResyncAbortMessage from '@site/docs/_common/resync-abort-message.mdx';

# 🔈 Event Listener

The Ocean framework provides built-in support for multiple event listeners. The event listener is used to receive events and resync requests from Port and forward them to the running Ocean integration.

## Ocean integration events

An Ocean integration needs to react and perform tasks based on events arriving both from Port, and from the 3rd-party service that it integrates with.

By configuring an event listener the integration will listen to and react to the following events sent **from Port**:

- Configuration update - the integration will use the data of the new configuration to perform a resync of information from the 3rd-party
- Resync request - the integration will perform a resync of data from the 3rd-party to Port based on the existing configuration

<EventListenerTypesList />

:::warning
The event listeners that are currently available do not support multiple instances of the same integration
:::

<ResyncAbortMessage />

## `POLLING`

```yaml showLineNumbers
eventListener:
  type: POLLING
  # Optional parameters
  resyncOnStart: True
  interval: 60
```

The polling event listener configures the Ocean integration to query Port at pre-determined intervals and check for any configuration changes or requests for data resync.

### Update flow

When an integration is configured with the polling event listener, the resync/update flow is:

1. The user updates the integration configuration in Port
2. The integration's polling interval expires and it performs another query to get the latest configuration
3. The integration detects a change in configuration or a resync requests and performs the resync

### Example

To use the polling event listener, set the `type` field to `POLLING` in the [integration configuration](../../develop-an-integration/integration-configuration.md):

```yaml showLineNumbers
eventListener:
  type: POLLING
```

### Available parameters

The parameters available to configure the polling event listener:

| Parameter       | Description                                                                                         | Default Value |
| --------------- | --------------------------------------------------------------------------------------------------- | ------------- |
| `resyncOnStart` | Whether to perform a manual resync from the 3rd party upon integration startup                      | `True`        |
| `interval`      | The time in seconds, between queries to Port to check for configuration changes and resync requests | `60`          |

:::warning
The `interval` parameter should be set to a value high enough to perform a full resync from the 3rd-party. Otherwise another resync process might start mid-way and create an infinite recurring resync

:::

## `KAFKA`

```yaml showLineNumbers
eventListener:
  type: KAFKA
  # Optional parameters
  brokers: "b-1-public.publicclusterprod.t9rw6w.c1.kafka.eu-west-1.amazonaws.com:9196"
  consumerPollTimeout: 1
```

The Kafka event listener configures the Ocean integration to check the customer's dedicated Kafka topic for any configuration changes or requests for data resync.

### Update flow

When an integration is configured with the Kafka event listener, the resync/update flow is:

1. The user updates the integration configuration in Port
2. Port publishes a message with the latest configuration to the customer's Kafka topic
3. The integration consumes the new message from the Kafka topic to get the latest configuration
4. The integration detects a change in configuration or a resync requests and performs the resync

### Example

To use the Kafka event listener, set the `type` field to `KAFKA` in the [integration configuration](../../develop-an-integration/integration-configuration.md):

```yaml showLineNumbers
eventListener:
  type: KAFKA
```

### Available parameters

The parameters available to configure the Kafka event listener:

| Parameter             | Description                                                                                                                  | Default Value                 |
| --------------------- | ---------------------------------------------------------------------------------------------------------------------------- | ----------------------------- |
| `brokers`             | A comma-separated list of Kafka brokers that the integration will use to check for configuration changes and resync requests | Port's Kafka broker addresses |
| `consumerPollTimeout` | The time in seconds, the Kafka consumer waits for messages before returning an empty response                                | `1`                           |

:::note
The Kafka event listener comes out-of-the-box with sane defaults which abstract the connection to Port's Kafka brokers. While it is possible to change them, it is usually unnecessary
:::

## `WEBHOOK`

```yaml showLineNumbers
eventListener:
  type: WEBHOOK
  appHost: "https://my-ocean-integration.example.com"
```

The webhook event listener configures the Ocean integration to react to web requests that provide it with the latest configuration changes or requests for data resync.

### Update flow

When an integration is configured with the webhook event listener, the resync/update flow is:

1. The user updates the integration configuration in Port
2. Port sends an HTTP request with latest configuration to the configured `appHost`
3. The integration receives the new request to get the latest configuration
4. The integration detects a change in configuration or a resync requests and performs the resync

### Example

To use the webhook event listener, set the `type` field to `WEBHOOK` and provide a the address used to contact the integration instance in the `appHost` field in the [integration configuration](../../develop-an-integration/integration-configuration.md):

```yaml showLineNumbers
eventListener:
  type: WEBHOOK
  appHost: "https://my-ocean-integration.example.com"
```

### Available parameters

The parameters available to configure the webhook event listener:

| Parameter | Description                         | Default Value |
| --------- | ----------------------------------- | ------------- |
| `appHost` | The URL of the integration instance | `null`        |

:::note
The `appHost` parameter must be a URL that Port can send requests to. Port's requests will always arrive from a closed-list of available IP addresses which can be found in Port's [security documentation](https://docs.port.io/create-self-service-experiences/security/)

:::
