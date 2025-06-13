---
title: Developing an Integration
sidebar_label: 🔧 Developing an Integration
---

# Introduction

In this guide, we'll walk through how to build a Port Ocean integration step by step. We'll use a Jira and Octopus integration as a practical example to demonstrate the concepts, but you can apply these same principles to build integrations for any system.

You'll learn how to:
1. Set up your integration project
2. Connect to third-party APIs
3. Map data to Port entities
4. Handle real-time updates
5. Test and deploy your integration

This guide assumes you've already:
- Installed the Ocean CLI
- Created a new integration project
- Set up your development environment

If you haven't done these steps yet, check out our [Getting Started](../getting-started/getting-started.md) guide first.

Get your gear 🤿 and let's dive 🏊‍♂️ in to building an integration!

## Understanding Ocean Integrations

An Ocean integration is essentially a connector that **extracts** data from external systems, **transforms** it to Port's entity model, and **synchronizes** it with your Port catalog. The framework handles the heavy lifting—you focus on the integration-specific logic.

## Ocean integration development flow

To develop and publish an integration you need to complete the following steps:

:::tip step order
These steps do not follow a specific order. Some steps only become relevant near the end of the integration's development, such as publishing.
:::

1. **Scaffold** a new integration, as seen in [getting started](../getting-started/getting-started.md#scaffolding-a-new-integration)
2. **Implement core logic** by adding the code and logic required for the new integration. [Create API clients](./implementing-an-api-client.md), [webhook processors](./implementing-webhooks.md), [resync functions](./handling-resyncs.md), and [define kinds configuration](./integration-configuration-and-kinds-in-ocean.md) in their respective directories.
3. **Configure integration spec** by updating the [`.port/spec.yml`](./defining-configuration-files.md) file with metadata, supported resource kinds, required parameters, and webhook configurations.
4. **Set up configuration** by updating the `integration.py` to add custom resource configs as described in [integration configuration](./integration-configuration-and-kinds-in-ocean.md).
5. **Define resource mappings** in the [`.port/resources`](./defining-configuration-files.md) directory including blueprints, entity mappings, and selectors for resource filtering.
6. **Test your integration** thoroughly with unit tests, integration tests, webhook processing tests, and resync functionality tests as described in [testing guide](./testing-the-integration.md).
7. **Document** your integration including README with setup instructions, CHANGELOG for version history, API documentation, and example configurations.
8. **Publish** your [integration](./publishing-your-integration.md) for others to use by creating a changelog, bumping version in `pyproject.toml`, and submitting a pull request to the Ocean repository.

:::tip Integration Performance
Be sure to review the integration [performance](./performance.md) and [code guidelines](./guidelines.md) to ensure your integration is efficient and well-written. Consider handling rate limiting, implementing pagination, using async code, supporting multi-account scenarios, managing webhook processing, and optimizing resync operations.
:::


