---
sidebar_position: 7
---


# Testing the Integration
Having completed the implementation of the integration, the next step is to test it. In this guide, we will learn how to test the integration to ingest data into our dashboard on Port.

## Prerequisites
Before we begin, ensure you have the following:

- `PORT_CLIENT_ID`: Your Port acccount client ID. You can find that by following the [Find Your Port Credentials guide](https://docs.port.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials).

- `PORT_CLIENT_SECRET`: Your Port account client secret. You can find that by following the [Find Your Port Credentials guide](https://docs.port.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials).

- `ACCESS_TOKEN`: Your GitHub access token. You can find that by following the [GitHub Authentication Documentation](https://docs.github.com/en/rest/authentication/authenticating-to-the-rest-api?apiVersion=2022-11-28).

- `BASE_URL`: The base URL for the GitHub API. If not provided, the default GitHub API URL, `https://api.github.com` will be used.

## Running the Integration
We will be running the integration locally using the Ocean CLI. You can run the integration with other means such as [Helm](../deployment/helm.md), [Terraform](../deployment/terraform.md), [Docker](../deployment//docker.md), and [ArgoCD](../deployment/argocd.md).

Create a `.env` file in the integration directory to store the environment variables required to run the integration. Add the following environment variables to the file:

<details>

<summary><b>Environment Variables</b></summary>

```shell showLineNumbers
OCEAN__PORT__CLIENT_ID=<your-port-client-secret>
OCEAN__PORT__CLIENT_SECRET=<your-port-client-secret>
OCEAN__INTEGRATION__CONFIG__ACCESS_TOKEN=<your-github-access-token>
OCEAN__EVENT_LISTENER__TYPE=POLLING
```

</details>

Now, it is time to do what we have been waiting for. Run the integration using the Ocean CLI:

```shell showLineNumbers
make run
```

You should see the integration running with the following output:

```shell
=====================================================================================
          ::::::::       ::::::::       ::::::::::           :::        ::::    :::
        :+:    :+:     :+:    :+:      :+:                :+: :+:      :+:+:   :+:
       +:+    +:+     +:+             +:+               +:+   +:+     :+:+:+  +:+
      +#+    +:+     +#+             +#++:++#         +#++:++#++:    +#+ +:+ +#+
     +#+    +#+     +#+             +#+              +#+     +#+    +#+  +#+#+#
    #+#    #+#     #+#    #+#      #+#              #+#     #+#    #+#   #+#+#
    ########       ########       ##########       ###     ###    ###    ####
=====================================================================================
By: Port.io
Setting sail... ⛵️⚓️⛵️⚓️ All hands on deck! ⚓️
🌊 Ocean version: 0.18.9
🚢 Integration version: 0.1.0-beta
2025-02-13 17:02:58.861 | INFO     | Registering resync event listener for kind organization
2025-02-13 17:02:58.861 | INFO     | Registering resync event listener for kind repository
2025-02-13 17:02:58.861 | INFO     | Registering resync event listener for kind pull_request
2025-02-13 17:02:58.862 | INFO     | Fetching integration with id: my-github-integration
2025-02-13 17:02:58.868 | INFO     | No token found, fetching new token
2025-02-13 17:02:58.868 | INFO     | Fetching access token for clientId: jqoQ34[REDACTED]
2025-02-13 17:03:00.759 | INFO     | Loading defaults from .port/resources
2025-02-13 17:03:00.764 | INFO     | Initializing integration at port
2025-02-13 17:03:00.764 | INFO     | Fetching integration with id: my-github-integration
2025-02-13 17:03:02.232 | INFO     | Checking for diff in integration configuration
2025-02-13 17:03:02.232 | INFO     | Updating integration with id: my-github-integration
2025-02-13 17:03:02.647 | INFO     | Found default resources, starting creation process
2025-02-13 17:03:02.648 | INFO     | Fetching blueprint with id: githubOrganization
2025-02-13 17:03:02.648 | INFO     | Fetching blueprint with id: githubRepository
2025-02-13 17:03:02.648 | INFO     | Fetching blueprint with id: githubPullRequest

```

Give it some time and it should sync the data from GitHub to your Port dashboard.

## Conclusion
Having developed and tested your integration, you can decide to use it locally or contribute to the Port community by following the guide in the next section.
