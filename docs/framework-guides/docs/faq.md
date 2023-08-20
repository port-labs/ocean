---
title: 🤔 FAQ
sidebar_position: 8
---

import TBD from './_common/tbd.md';

## Frequently Asked Questions

Welcome to our FAQ page! Here are some common questions and answers to help you understand and navigate through our
integration framework.

### What is required to develop an integration?

If you want to get started with how to develop an integration, you can check out our [Getting Started](/getting-started)
guide.

### How can I check my integration?

To start testing your integration, you can use the `ocean sail` command. This command will run your integration locally
and will allow you to test it.
Then proceed with triggering the integration as mentioned in
the [Trigger Your Integration](/develop-an-integration/trigger-your-integration) guide.

### What's the process for debugging my integration?

To debug your integration follow the steps in
the [Debugging](/develop-an-integration/update-integration-code#debugpy---debug-an-integration) guide.

### Is it necessary to publish my integration?

No, publishing your integration is optional. Although, by publishing your integration, you can share it with other users
and organizations and gain our support over the integration logic.

### How can I publish my integration?

To publish your integration, follow the steps in the [Publishing](/develop-an-integration/publish-your-integration)
guide.

### What is the purpose of Ocean?

You can read about the purpose of Ocean in our [Ocean Overview](/ocean-overview) guide.

### How do I remove my integration?

You can remove your integration by triggering the DELETE method on the integration's endpoint on the Port API.

:::caution

Deleting an integration will not stop the service from running and ingesting data. To stop the service, you need to stop
the process running the integration.

:::

### What steps are involved in setting up Kafka for my integration?

You can read all about setting up Kafka for your integration in [Kafka](/framework/features/event-listener#kafka) page.

### What prerequisites are there for developing my integration?

To develop your integration you need to know how you would like to integrate to the product the integration will be for,
familiarity with Python programming language and a basic understanding of the Ocean Framework.

### How can I write an integration with live events?

You can read all about writing an integration with live events in our [Live Events](/framework/features/live-events)

### My new integration is experiencing sluggish performance. Any solutions?

You can read about how to improve your integration's performance in our [Performance](/framework/develop-an-integration-performance) page.

### My integration isn't functioning correctly. What should I do?

You should first check the logs of your integration to see if there are any errors. If there are no errors, you try to debug your integration.

You can read about debugging your integration in our [Debugging](/develop-an-integration/update-integration-code#debugpy---debug-an-integration) page.

If you are still experiencing issues, you can contact us at any of the following:
- [Slack](https://slack.ocean.dev)
- [Mail](mailto:support@getport.io)
- [Live chat](https://www.getport.io)

### What level of performance can I expect from Ocean?

<TBD />

### How do I incorporate custom fields into my integration?

Extend the integration configuration by following the steps in the [Integration Configuration](/develop-an-integration/integration-configuration) page.

### What's the approach to supporting GitOps in my integration?

<TBD />

### What responsibilities should my integration logic have?

Your integration logic should cover data extraction and error handling of the third party application.

Ocean will take care of the rest 😁.

### Can I create a private integration exclusively for my organization?

Yes, you can develop a private integration restricted to your organization's use, ensuring its privacy and exclusivity.

:::note 

Please note that private integrations are not yet supported and their usage will exclusively be accessible through the Port API.

:::

### How can I listen to action triggers within my integration?

<TBD />

### Am I limited to using only Python for writing integrations?

At the moment, yes. We are working on supporting more languages in the future.
