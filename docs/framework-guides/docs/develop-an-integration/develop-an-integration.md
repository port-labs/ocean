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

1. **Scaffold** a new integration, as seen in [getting started](../getting-started/getting-started.md#scaffold)
2. **Implement core logic** by adding the [code and logic](./update-integration-code.md) required for the new integration. The heart of your integration is the `on_resync` method that fetches data from your target system.
3. **Configure integration spec** by updating the [`.port/spec.yml`](./integration-spec-and-default-resources.md#specyaml-file) file with metadata, supported resource kinds, and required parameters
4. **Set up configuration** by updating the [`config.yaml`](./integration-configuration.md) file with connection parameters and settings
5. **Define resource mappings** (Optional) Add default definitions to the [`.port/resources`](./integration-spec-and-default-resources.md#port-folder) directory such as [default blueprints](./integration-spec-and-default-resources.md#blueprintsjson-file) and [entity mappings](./integration-spec-and-default-resources.md#port-app-configyml-file)
6. **Test your integration** thoroughly with unit tests and real data
7. **Document** your integration including README and changelog
8. **Publish** your [integration](./publish-an-integration.md) for others to use

:::tip Integration Performance
Be sure to review the integration [performance](./performance.md) and [code guidelines](./guidelines.md) to ensure your integration is efficient and well-written.
:::


