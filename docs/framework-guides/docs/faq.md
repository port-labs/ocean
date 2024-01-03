---
title: FAQ
sidebar_label: 🤔 FAQ
sidebar_position: 9
---

# 🤔 FAQ

import TBD from './\_common/tbd.md';

Welcome to our FAQ page! Here are some common questions and answers to help you understand and navigate through the Ocean
integration framework.

## What is the purpose of Ocean?

You can read about the purpose of Ocean in the [Ocean overview](./ocean-overview.md) section.

## What is required to develop an integration?

To get started with the Ocean framework and develop an integration, the best place to start is the [getting started](./getting-started/getting-started.md)
guide.

## How can I test my integration?

To start testing your integration, you can use the `ocean sail` command. This command will run your integration locally
and will allow you to test it and verify its interaction and behavior both with the integrated service and Port.

Then proceed with triggering the integration as mentioned in
the [trigger your integration](/develop-an-integration/trigger-your-integration) guide.

## How can I debug my integration?

To debug your integration follow the steps in
the [debugging](/develop-an-integration/update-integration-code#debugpy---debug-an-integration) guide.

## Is it necessary to publish my integration?

No, publishing your integration is optional. But we highly encourage the community to contribute and publish their integrations so that other users can benefit from them as well.

## How can I publish my integration?

To publish your integration, follow the steps in the [publishing](./develop-an-integration/publish-an-integration.md)
guide.

## How do I remove my integration from Port?

You can remove your integration by sending an HTTP DELETE method to the `https://api.getport.io/v1/integration/<INTEGRATION_IDENTIFIER>` endpoint in [Port's API](https://api.getport.io/static/index.html#/Integrations/delete_v1_integration__identifier_).

:::warning
Deleting an integration will not stop the service from running and ingesting data. To stop the service, you need to stop
the process running the integration.
:::

## What steps are involved in setting up Kafka for my integration?

You can read all about setting up Kafka for your integration in the [Kafka event listener](./framework/features/event-listener.md#kafka) page.

## What prerequisites are there to develop my integration?

To develop an integration you need familiarity with the Python programming language and basic understanding of the Ocean framework. In addition, you need to understand how to connect your integration's code with the 3rd-party service that it integrates with.

## How can I write an integration with live events?

You can read all about writing an integration with live events in our [Live events](./framework/features/live-events) guide.

## What level of performance can I expect from Ocean?

<TBD />

## My integration is experiencing sluggish performance. Any solutions?

You can read about how to improve your integration's performance in our [Performance](/develop-an-integration/performance) page.

## My integration isn't functioning correctly. What should I do?

You should first check the logs of your integration to see if there are any errors. If there are no errors, you try to debug your integration.

You can read about debugging your integration in our [Debugging](/develop-an-integration/update-integration-code#debugpy---debug-an-integration) page.

If you are still experiencing issues, you can contact us at any of the following:

- [Slack](https://www.getport.io/community)
- [Mail](mailto:support@getport.io)
- [Live Chat](https://www.app.getport.io)

## How do I incorporate custom fields into my integration?

Extend the integration configuration by following the steps in the [Integration Configuration](/develop-an-integration/integration-configuration) page.

## How can I add support GitOps operations in my integration?

<TBD />

## What tasks should my integration logic handle?

Your integration logic should cover data extraction and error handling of the 3rd-party application.

Ocean will take care of the rest 😁.

## Can I create a private integration exclusively for my organization?

Yes, you can develop a private integration restricted to your organization's use, ensuring its privacy and exclusivity.

:::note
Please note that private integrations are not yet supported.
:::

## How can I listen to action triggers within my integration?

<TBD />

## Am I limited to using only Python for writing integrations?

At the moment, yes. We are working on supporting more languages in the future.
