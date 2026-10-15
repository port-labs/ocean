# Google Cloud Platform integration

An integration used to import gcp resources into Port.

## Install & use the integration Locally

### Create a service account with the following permissions

**IMPORTANT- These can be granted at a Project/Folder/Organization Level, and the integration will digest all resources of all projects with these permissions.**

- cloudasset.assets.exportResource
- cloudasset.assets.listCloudAssetFeeds
- cloudasset.assets.listResource
- cloudasset.assets.searchAllResources
- cloudasset.feeds.create
- cloudasset.feeds.list
- pubsub.topics.list
- pubsub.topics.get
- resourcemanager.projects.get
- resourcemanager.projects.list
- resourcemanager.folders.get
- resourcemanager.folders.list
- cloudasset.assets.searchAllIamPolicies (only for the `iam.googleapis.com/Policy` kind)

#### Suggested way of achieving this

1. Create a service account in a **project**
2. Create a role in the scope you want the integration to run (= Make sure you selected the right resource in the top left corner).
3. Grant the role to the service account (can be done via the Manage Resources in IAM)

### IAM allow policy bindings

Kind `iam.googleapis.com/Policy` syncs explicit IAM allow-policy bindings from Cloud Asset Inventory [`searchAllIamPolicies`](https://cloud.google.com/asset-inventory/docs/reference/rest/v1/TopLevel/searchAllIamPolicies). Each raw item is one binding member on one resource (`resource`, `role`, `member`). It does not call Policy Analyzer and does not include inherited access.

Other GCP kinds stay on `searchAllResources` or their product APIs. This kind is separate so those mappings keep the same raw shape.

`selector.assetTypes` is required. Policies are read once per accessible project, the same scope as other resource kinds. `selector.policyQuery` is optional and is sent only to `searchAllIamPolicies`. It is not the JQ `selector.query`, and it is not applied to any other Cloud Asset API. Example: `memberTypes:serviceAccount`. See the [IAM policy search syntax](https://cloud.google.com/asset-inventory/docs/searching-iam-policies).

`searchAllIamPolicies` defaults to 400 requests per minute per consumer project. The integration rate-limits that quota separately from `searchAllResources` and uses a page size of 500.

Real-time asset feeds stay on `--content-type=resource` and update resource kinds. They do not update `iam.googleapis.com/Policy`; that kind is resync-only. Workload Identity (`iam.gke.io/gcp-service-account` on a Kubernetes service account) is not an IAM allow policy.

```yaml
- kind: iam.googleapis.com/Policy
  selector:
    query: 'true'
    assetTypes:
      - cloudresourcemanager.googleapis.com/Project
      - iam.googleapis.com/ServiceAccount
    policyQuery: memberTypes:serviceAccount
  port:
    entity:
      mappings:
        identifier: .resource + "|" + .role + "|" + .member + "|" + (.condition.expression // "")
        title: .member
        blueprint: '"gcpIamPolicyBinding"'
        properties:
          role: .role
          member: .member
          resource: .resource
          assetType: .asset_type
        relations:
          project: .__project.name
```

`assetTypes` selects the resource the allow policy is attached to. `policyQuery: memberTypes:serviceAccount` keeps Google service account principals. A project asset type plus that query is which service accounts have which role on which project. Include the condition expression in the identifier when the same member and role can appear twice on one resource. Project-scoped results include `__project`.

### Real time requirements

1. Create a pubsub topic in a **project**
2. Create a subscription connected to this topic:
    1. Delivery type: PUSH
        1. Insert the url to the ocean app on this format: `https://<your-url>/integration/events`
        2. You can use ngrok as a local ingress
3. Create Assets feed pointing to this topic:
    
    ```
    gcloud asset feeds create <FEED_ID> 
    	--pubsub-topic=<your_pubsub_topic> 
    	--asset-types=<ASSET_TYPES>
    	--content-type=resource
    	--condition-expression=<CONDITION_EXPRESSION> 
    	<--folder=FOLDER_ID | --organization=ORGANIZATION_ID | --project=PROJECT_ID>
    ```
    
    - **ASSETS_FEED_TOPIC_NAME** - The name of the topic created for real-time events. The format is: `projects/<your-project-id>/topics/<your-topic-name>`
    - **ASSET_TYPES** - Comma separated list of the types you want to have real-time events for. The types can be found here: https://cloud.google.com/asset-inventory/docs/supported-asset-types . For example, if I want to fetch real-time events for buckets, VM instances and subscriptions, the ASSETS_FEED_ASSETS_TYPES should be:
        - `[storage.googleapis.com/Bucket,compute.googleapis.com/Instance,pubsub.googleapis.com/Subscription]`
    - **FOLDER/ORGANIZATION/PROJECT**  - This depends on what resolution you want the real time events for. **NOTICE that for each unique folder/project you’ll have to create another topic+subscription+feed.**
    - **CONDITION_EXPRESSION** - Quote surrounded query that controls what types of events create a feed event. For more information: https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes-with-condition
        - Suggestion: `"'<YOUR PROJECT/FOLDER/ORGANIZATION ID>' in temporal_asset.asset.ancestors"`

### Starting up Ocean

1. Use service account’s permissions
    1. Create a key from the Service-account window (this will download a json file) 
    2. export the location of this file in an environment variable:
        1. `export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service_account_file.json`
2. Export Port’s credentials
    1. `export PORT_CLIENT_ID=<your_port_client_id>`
    2. `export PORT_CLIENT_SECRET=<your_port_client_secret>`
3. Run Ocean! 
    1. clone the Ocean repo https://github.com/port-labs/ocean
    2. `cd integrations/gcp`
    3. `ocean sail -l DEBUG`

### Known limitations

- Quoting the GCP docs https://cloud.google.com/asset-inventory/docs/monitoring-asset-changes#limitations:
    - *It can take up to 10 minutes for any feed creation, update, or deletion to take effect.*
- All of the resource delays as the are brought here: https://cloud.google.com/asset-inventory/docs/supported-asset-types



#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)