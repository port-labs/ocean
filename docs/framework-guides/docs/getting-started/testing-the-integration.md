---
sidebar_position: 7
---


# 🧪 Testing the Integration
Having completed the implementation of the integration, the next step is to test it. In this guide, we will learn how to test the integration to ingest data into our dashboard on Port.

## Prerequisites
Before we begin, ensure you have the following:

- `PORT_CLIENT_ID`: Your Port acccount client ID. You can find that by following the [Find Your Port Credentials guide](https://docs.port.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials).

- `PORT_CLIENT_SECRET`: Your Port account client secret. You can find that by following the [Find Your Port Credentials guide](https://docs.port.io/build-your-software-catalog/custom-integration/api/#find-your-port-credentials).

- `JIRA_HOST`: Your Jira host URL. For example, `https://example.atlassian.net`.

- `ATLASSIAN_USER_EMAIL`: The email of the user used to query Jira.

- `ATLASSIAN_USER_TOKEN`: The token of the user used to query Jira. You can configure the user token on the [Atlassian account page](https://id.atlassian.com/manage-profile/security/api-tokens).

- `BASE_URL`: This is the URL mapped to the running integration. This is only required if the integration has live events enabled. Since we're running the integration locally, we can use Ngrok to expose the local server to the internet. [Install Ngrok](https://ngrok.com/download) and run `ngrok http 8000` to get the URL. The integration will be running on port 8000.


## Running the Integration
We will be running the integration locally using the Ocean CLI. You can run the integration with other means such as [Helm](../deployment/helm.md), [Terraform](../deployment/terraform.md), [Docker](../deployment//docker.md), and [ArgoCD](../deployment/argocd.md).

Create a `.env` file in the integration directory to store the environment variables required to run the integration. Add the following environment variables to the file:

<details>

<summary><b>Environment Variables</b></summary>

```shell showLineNumbers title=".env"
OCEAN__PORT__CLIENT_ID=<your-port-client-secret>
OCEAN__PORT__CLIENT_SECRET=<your-port-client-secret>
OCEAN__EVENT_LISTENER__TYPE=POLLING
OCEAN__BASE_URL=<your-ngrok-url>
OCEAN__INTEGRATION__CONFIG__JIRA_HOST=<your-jira-host>
OCEAN__INTEGRATION__CONFIG__ATLASSIAN_USER_EMAIL=<your-atlassian-user-email>
OCEAN__INTEGRATION__CONFIG__ATLASSIAN_USER_TOKEN=<your-atlassian-user-token>

```

</details>

Now, it is time to do what we have been waiting for. Run the integration using the Ocean CLI:

```console showLineNumbers title="bash"
$ make run
```

You should see the integration running with the following output:

<details>

<summary><b>Integration Output (Click to expand)</b></summary>

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
🌊 Ocean version: 0.21.0
🚢 Integration version: 0.1.0-beta
2025-03-13 11:30:56.585 | INFO     | Registering resync event listener for kind project | {}
2025-03-13 11:30:56.585 | INFO     | Registering resync event listener for kind issue | {}
2025-03-13 11:30:56.585 | DEBUG    | Registering <function on_start at 0x7031fe965c60> as a start event listener | {}
2025-03-13 11:30:56.589 | DEBUG    | Validating integration runtime | {}
2025-03-13 11:30:56.589 | INFO     | Fetching integration with id: my-jira-integration | {}
2025-03-13 11:30:56.594 | INFO     | No token found, fetching new token | {}
2025-03-13 11:30:56.594 | INFO     | Fetching access token for clientId: jqoQ34[REDACTED] | {}
2025-03-13 11:30:58.658 | INFO     | Loading defaults from .port/resources | {'defaults_dir': PosixPath('.port/resources')}
2025-03-13 11:30:58.675 | INFO     | Fetching provision enabled integrations | {}
2025-03-13 11:31:00.412 | INFO     | Fetching organization feature flags | {}
2025-03-13 11:31:00.840 | INFO     | Setting resources origin to be Port (integration jira is supported) | {}
2025-03-13 11:31:00.840 | INFO     | Resources origin is set to be Port, verifying integration is supported | {}
2025-03-13 11:31:00.840 | INFO     | Port origin for Integration is not supported, changing resources origin to use Ocean | {}
2025-03-13 11:31:00.840 | INFO     | Initializing integration at port | {}
2025-03-13 11:31:00.841 | INFO     | Fetching integration with id: my-jira-integration | {}
2025-03-13 11:31:01.260 | INFO     | Integration does not exist, Creating new integration with default mapping | {}
2025-03-13 11:31:01.261 | INFO     | Creating integration with id: my-jira-integration | {}
2025-03-13 11:31:02.130 | INFO     | Checking for diff in integration configuration | {}
2025-03-13 11:31:02.131 | INFO     | Updating integration with id: my-jira-integration | {}
2025-03-13 11:31:02.133 | DEBUG    | Ingesting logs | {}
2025-03-13 11:31:02.133 | INFO     | Fetching integration with id: my-jira-integration | {}
2025-03-13 11:31:02.545 | INFO     | Found default resources, starting creation process | {}
2025-03-13 11:31:02.545 | INFO     | Fetching blueprint with id: jiraProject | {}
2025-03-13 11:31:02.546 | INFO     | Fetching blueprint with id: jiraIssue | {}
2025-03-13 11:31:04.019 | DEBUG    | Failed to send logs to Port with error: Object of type PosixPath is not JSON serializable | {}
2025-03-13 11:31:04.310 | INFO     | Creating blueprint with id: jiraProject | {}
2025-03-13 11:31:04.312 | INFO     | Creating blueprint with id: jiraIssue | {}
2025-03-13 11:31:06.184 | INFO     | Patching blueprint with id: jiraProject | {}
2025-03-13 11:31:06.186 | INFO     | Patching blueprint with id: jiraIssue | {}
2025-03-13 11:31:06.802 | INFO     | Patching blueprint with id: jiraProject | {}
2025-03-13 11:31:06.805 | INFO     | Patching blueprint with id: jiraIssue | {}
2025-03-13 11:31:09.202 | DEBUG    | Ingesting logs | {}
INFO:     Started server process [3943128]
INFO:     Waiting for application startup.
2025-03-13 11:31:09.220 | INFO     | Starting integration | {'integration_type': 'jira'}
2025-03-13 11:31:09.221 | INFO     | Initializing integration components | {}
2025-03-13 11:31:09.221 | INFO     | Event started | {'event_trigger_type': 'machine', 'event_kind': 'start', 'event_id': '14cc4bbf-298d-404e-b317-4d5c15d65403', 'event_parent_id': None, 'event_resource_kind': None}
2025-03-13 11:31:09.222 | INFO     | Starting Port Ocean Jira integration | {'event_trigger_type': 'machine', 'event_kind': 'start', 'event_id': '14cc4bbf-298d-404e-b317-4d5c15d65403', 'event_parent_id': None, 'event_resource_kind': None}
2025-03-13 11:31:12.105 | INFO     | Ocean real time reporting webhook created | {'event_trigger_type': 'machine', 'event_kind': 'start', 'event_id': '14cc4bbf-298d-404e-b317-4d5c15d65403', 'event_parent_id': None, 'event_resource_kind': None}
2025-03-13 11:31:12.105 | INFO     | Event finished | {'event_trigger_type': 'machine', 'event_kind': 'start', 'event_id': '14cc4bbf-298d-404e-b317-4d5c15d65403', 'event_parent_id': None, 'event_resource_kind': None, 'success': True, 'time_elapsed': 2.88437}
2025-03-13 11:31:12.106 | INFO     | Initializing event listener | {}
2025-03-13 11:31:12.106 | INFO     | Found event listener type: polling | {}
2025-03-13 11:31:12.106 | INFO     | Setting up Polling event listener with interval: 60 | {}
2025-03-13 11:31:12.106 | INFO     | Initializing integration components | {}
2025-03-13 11:31:12.106 | INFO     | Polling event listener iteration after 60. Checking for changes | {}
2025-03-13 11:31:12.107 | INFO     | Fetching integration with id: my-jira-integration | {}
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000 (Press CTRL+C to quit)
2025-03-13 11:31:12.441 | DEBUG    | Logs successfully ingested | {}
2025-03-13 11:31:13.395 | INFO     | Detected change in integration, resyncing | {}
2025-03-13 11:31:13.396 | DEBUG    | Updating integration resync state with: {'status': 'running', 'lastResyncEnd': None, 'lastResyncStart': '2025-03-13T10:31:13.396147+00:00', 'nextResync': None, 'intervalInMinuets': None} | {}
2025-03-13 11:31:13.987 | INFO     | Integration resync state updated successfully | {}
2025-03-13 11:31:13.987 | INFO     | Resync was triggered | {}
2025-03-13 11:31:13.987 | INFO     | Event started | {'event_trigger_type': 'machine', 'event_kind': 'resync', 'event_id': '1567d7df-2b1d-4da3-ab97-ac0c4c5a3705', 'event_parent_id': None, 'event_resource_kind': None}
2025-03-13 11:31:13.987 | INFO     | Fetching port app config | {'event_trigger_type': 'machine', 'event_kind': 'resync', 'event_id': '1567d7df-2b1d-4da3-ab97-ac0c4c5a3705', 'event_parent_id': None, 'event_resource_kind': None}
2025-03-13 11:31:13.988 | INFO     | Fetching integration with id: my-jira-integration | {'event_trigger_type': 'machine', 'event_kind': 'resync', 'event_id': '1567d7df-2b1d-4da3-ab97-ac0c4c5a3705', 'event_parent_id': None, 'event_resource_kind': None}
2025-03-13 11:31:14.298 | INFO     | Resync will use the following mappings: {'enable_merge_entity': True, 'delete_dependent_entities': True, 'create_missing_related_entities': True, 'entity_deletion_threshold': 0.9, 'resources': [{'kind': 'project', 'selector': {'query': 'true', 'expand': 'insight'}, 'port': {'entity': {'mappings': {'identifier': '.key', 'title': '.name', 'blueprint': '"jiraProject"', 'team': None, 'properties': {'url': '(.self | split("/") | .[:3] | join("/")) + "/projects/" + .key', 'totalIssues': '.insight.totalIssueCount'}, 'relations': {}}}, 'items_to_parse': None}}, {'kind': 'issue', 'selector': {'query': 'true', 'jql': '(statusCategory != Done) OR (created >= -1w) OR (updated >= -1w)', 'fields': '*all'}, 'port': {'entity': {'mappings': {'identifier': '.key', 'title': '.fields.summary', 'blueprint': '"jiraIssue"', 'team': None, 'properties': {'url': '(.self | split("/") | .[:3] | join("/")) + "/browse/" + .key', 'status': '.fields.status.name', 'issueType': '.fields.issuetype.name', 'components': '.fields.components', 'creator': '.fields.creator.emailAddress', 'priority': '.fields.priority.name', 'labels': '.fields.labels', 'created': '.fields.created', 'updated': '.fields.updated', 'resolutionDate': '.fields.resolutiondate'}, 'relations': {'project': '.fields.project.key', 'parentIssue': '.fields.parent.key', 'subtasks': '.fields.subtasks | map(.key)', 'assignee': '.fields.assignee.accountId', 'reporter': '.fields.reporter.accountId'}}}, 'items_to_parse': None}}]} | {'event_trigger_type': 'machine', 'event_kind': 'resync', 'event_id': '1567d7df-2b1d-4da3-ab97-ac0c4c5a3705', 'event_parent_id': None, 'event_resource_kind': None}

```

</details>

Give it some time and it should sync the data from Jira to your Port dashboard.

## Conclusion
Having developed and tested your integration, you can decide to use it locally or contribute to the Port community by following the guide in the next section.

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::
