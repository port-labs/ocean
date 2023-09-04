---
title: Terraform Deployment
sidebar_label: 🌍 Terraform
sidebar_position: 2
---

import IntegrationsLibraryLink from './\_integration-list-link.md';
import UIInstallation from './\_ui-installation-process.md';
import CheckInstallation from './\_check_installation.md';

# 🌍 Terraform Deployment

This guide will walk you through deploying an integration of the Ocean framework using [Terraform](https://www.terraform.io/) and your favorite cloud
provider.

<CheckInstallation/>

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) installed
- Credentials for the cloud provider you want to use
- [Port](https://app.getport.io) organization for the the Client ID and Client Secret
- The integration's required configurations

## Deploying the integration

<UIInstallation/>

All installation options can be found in the Ocean integration factory Terraform
provider [examples](https://registry.terraform.io/modules/port-labs/integration-factory/ocean/latest).

<IntegrationsLibraryLink/>

:::info Integration Configuration
The generic configuration for integrations can be found in
the [Integration Configuration](../develop-an-integration/integration-configuration.md) guide.
:::

:::info Event Listener
More information about the available event listener types and optional configurations can be found in
the [Event Listeners](../framework/features/event-listener.md) guide.
:::
