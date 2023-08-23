---
title: Terraform deployment
sidebar_label: 🌍 Terraform
sidebar_position: 1
---

import IntegrationsLibraryLink from './_integration-list-link.md';
import UIInstallation from './_ui-installation-process.md';
import CheckInstallation from './_check_installation.md';

# 🌍 Terraform deployment

This guide will walk you through deploying an integration of the Ocean framework using Terraform and your favorite
provider.

<CheckInstallation/>

## Prerequisites

- [Terraform](https://www.terraform.io/downloads.html) installed
- Proper Credentials for the provider you want to use
- [Port](https://app.getport.io) organization for the the Client ID and Client Secret
- The integration required configurations

## Deploying the integration

<UIInstallation/>

All installation options can be found in the Ocean Integration factory Terraform
Provider [examples](https://registry.terraform.io/modules/port-labs/integration-factory/ocean/latest).

<IntegrationsLibraryLink/>

:::info Integration Configuration
The generic configuration for integrations can be found in
the [Integration Configuration](../develop-an-integration/integration-configuration.md) guide.
:::

:::info Event Listener
More information about the available event listener types and optional configurations can be found in
the [Event Listeners](../framework/features/event-listener.md) guide.
:::