---
title: ArgoCD Deployment
sidebar_label: 🐙 ArgoCD
sidebar_position: 4
---

import IntegrationsLibraryLink from './\_integration-list-link.md';
import UIInstallation from './\_ui-installation-process.md';
import CheckInstallation from './\_check_installation.md';
import Image from "@theme/IdealImage";
import Credentials from "/static/img/credentials-modal.png"

# ⚓️ ArgoCD Deployment

This guide will walk you through deploying an integration of the Ocean framework using ArgoCD, utilizing it's [Helm Capabilities](https://argo-cd.readthedocs.io/en/stable/user-guide/helm/).

:::info
- You can observe the Helm chart and the available parameters [here](https://github.com/port-labs/helm-charts/tree/main/charts/port-ocean).
- For the full chart versions list refer to the [Releases](https://github.com/port-labs/helm-charts/releases?q=port-ocean&expanded=true) page.
:::

<CheckInstallation/>

## Prerequisites

- [kubectl](https://kubernetes.io/docs/tasks/tools/#kubectl) must be installed to apply your installation manifest.
- [Helm](https://helm.sh/docs/intro/install/) installed.
- [Kubernetes](https://kubernetes.io/docs/tasks/tools/) cluster to deploy the integration to.
- [ArgoCD](https://argoproj.github.io/cd/) must be installed in your Kubernetes cluster. Please refer to ArgoCD's [documentation](https://argo-cd.readthedocs.io/en/stable/getting_started/#1-install-argo-cd) for further details about the installation.
- The integration's required configurations.
- Your organization [Port credentials](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/api/#find-your-port-credentials).

:::tip
<details>
<summary>Get your Port credentials</summary>

To get your Port API credentials go to your [Port application](https://app.getport.io), click on the `...` button in the top right corner, and select `Credentials`. Here you can view and copy your `CLIENT_ID` and `CLIENT_SECRET`:

<center>

<Image img={Credentials} style={{ width: 500 }} />

</center>
</details>
:::

:::warning
This guide will install the ArgoCD Application using the current Kubernetes context. Make sure you have the correct context set before continuing.
:::

## Deploying the integration

1. In your git repo, create a directory called `argocd`.
```bash showLineNumbers
mkdir argocd
```

2. Inside your `argocd` directory create another directory for the current installation. For our example we use `my-ocean-integration`.
```bash showLineNumbers
mkdir -p argocd/my-ocean-integration
```

3. Create a `values.yaml` file in your `my-ocean-integration` directory, with the relevant content for your integration and commit the changes to your git repository:

:::note
Remember to replace the placeholders for `THE_INTEGRATION_WANTED_IDENTIFIER` `WHICH_INTEGRATION_TO_DEPLOY` `EVENT_LISTENER_TYPE` `SECRET_VALUE` and `CONFIG_VALUE`.
:::
```yaml showLineNumbers
initializePortResources: true
integration:
  identifier: THE_INTEGRATION_WANTED_IDENTIFIER 
  type: WHICH_INTEGRATION_TO_DEPLOY
  eventListener:
    type: EVENT_LISTENER_TYPE
  secrets:
    INTEGRATION_SPECIFIC_SECRETS: SECRET_VALUE
  config:
    INTEGRATION_SPECIFIC_CONFIG: CONFIG_VALUE
```
:::tip Integration Configuration
The generic configuration for integrations can be found in
the [integration configuration](../develop-an-integration/integration-configuration.md) guide.
:::

:::tip Event Listener
More information about the available event listener types and optional configurations can be found in
the [event listeners](../framework/features/event-listener.md) guide.
:::

4. Install the `my-ocean-integration` ArgoCD Application by creating the following `my-ocean-integration.yaml` manifest:
:::note
Remember to replace the placeholders for `YOUR_PORT_CLIENT_ID` `YOUR_PORT_CLIENT_SECRET` and `YOUR_GIT_REPO_URL`.

Multiple sources ArgoCD documentation can be found [here](https://argo-cd.readthedocs.io/en/stable/user-guide/multiple_sources/#helm-value-files-from-external-git-repository).
:::

<details>
  <summary>ArgoCD Application</summary>

```yaml showLineNumbers
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: my-ocean-integration
  namespace: argocd
spec:
  destination:
    namespace: my-ocean-integration
    server: https://kubernetes.default.svc
  project: default
  sources:
  - repoURL: 'https://port-labs.github.io/helm-charts/'
    chart: port-ocean
    targetRevision: 0.1.14
    helm:
      valueFiles:
      - $values/argocd/my-ocean-integration/values.yaml
      parameters:
        - name: port.clientId
          value: YOUR_PORT_CLIENT_ID
        - name: port.clientSecret
          value: YOUR_PORT_CLIENT_SECRET
  - repoURL: YOUR_GIT_REPO_URL
    targetRevision: main
    ref: values
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
    syncOptions:
    - CreateNamespace=true
```

</details>
<br/>

5. Apply your application manifest with `kubectl`:
```bash showLineNumbers
kubectl apply -f my-ocean-integration.yaml
```

## Advanced configuration
The Ocean framework supports [advanced configuration](../framework/advanced-configuration.md) using environment variables. The Ocean Helm chart allows setting these variables using Helm parameters. This can be done by making changes to your `values.yaml` file and committing them in your git repository.

For example add to your `values.yaml` file:
```yaml showLineNumbers
# The rest of the configuration
# ...
extraEnvs:
  - name: HTTP_PROXY
    value: http://my-proxy.com:1111
```