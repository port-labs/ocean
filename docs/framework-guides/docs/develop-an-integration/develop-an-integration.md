---
title: 🔧 Develop an Integration
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

1. Scaffold a new integration, as seen in [getting started](../getting-started/getting-started.md#scaffold)
2. Add any required code libraries and the code and logic required for the new integration
3. Update the `config.yml` file with default configuration and parameters for the integration
4. Update the `.port/spec.yml` file with metadata of the integration, including the provided kinds and required parameters
5. (Optional) Add default definitions to the `.port/resources` directory such as default blueprints and integration mapping
6. Create the necessary documentation for the new integration including the README and a changelog
7. [Publish](./publish-an-integration.md) the integration
