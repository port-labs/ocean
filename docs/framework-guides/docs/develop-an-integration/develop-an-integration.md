---
title: Develop an Integration
sidebar_label: 🔧 Develop an Integration
---

# 🔧 Develop an Integration

This section builds on the [getting started](../getting-started/getting-started.md) section which shows how to install the Ocean CLI and scaffold a new integration to begin development.

This section dives deeper into the different components that make up an Ocean integration, as well as examples on how to configure and test them.

Finally, this section covers the integration publishing process.

## Ocean integration development flow

To develop and publish an integration you need to complete the following steps:

:::tip step order
These steps do not follow a specific order. Some steps only become relevant near the end of the integration's development, such as publishing.
:::

1. **Initialize Your Integration**
   - Scaffold a new integration using the steps in the [getting started guide](../getting-started/getting-started.md#scaffold)
   - This creates the basic structure for your integration

2. **Implement Core Functionality**
   - Add required code libraries
   - Implement your [integration logic](./update-integration-code.md)
   - Follow the [performance guidelines](./performance.md) and [code standards](./guidelines.md)

3. **Configure Integration Settings**
   - Update [`.port/spec.yml`](./integration-spec-and-default-resources.md#specyaml-file) with:
     - Integration metadata
     - Supported resource kinds
     - Required parameters
   - Set up [`config.yaml`](./integration-configuration.md) with:
     - Configuration parameters
     - Default settings

4. **Add Resources (Optional)**
   - In [`.port/resources`](./integration-spec-and-default-resources.md#port-folder) directory:
     - Add [default blueprints](./integration-spec-and-default-resources.md#blueprintsjson-file)
     - Configure [integration mapping](./integration-spec-and-default-resources.md#port-app-configyml-file)

5. **Documentation and Release**
   - Create comprehensive README
   - Maintain a changelog
   - [Publish](./publish-an-integration.md) your integration
