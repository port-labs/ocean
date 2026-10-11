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
- cloudasset.assets.searchAllIamPolicies (only when `selector.contentType` is `IAM_POLICY` and `selector.assetQuery` is set)
- cloudasset.assets.listIamPolicy (for `contentType: IAM_POLICY` without `assetQuery`)
- cloudasset.assets.listOrgPolicy (for `contentType: ORG_POLICY`)
- cloudasset.assets.listAccessPolicy (for `contentType: ACCESS_POLICY`)
- cloudasset.assets.listOSInventories (for `contentType: OS_INVENTORY`)

#### Suggested way of achieving this

1. Create a service account in a **project**
2. Create a role in the scope you want the integration to run (= Make sure you selected the right resource in the top left corner).
3. Grant the role to the service account (can be done via the Manage Resources in IAM)

### Cloud Asset content types

`selector.contentType` chooses which Cloud Asset Inventory record to read for an asset kind. The default is `RESOURCE`, which keeps the current `searchAllResources` sync and the same raw resource shape.

| contentType | API | Raw block to expand | Server-side `assetQuery` |
| --- | --- | --- | --- |
| `RESOURCE` (default) | `searchAllResources` | The resource itself | Yes. [Resource search syntax](https://cloud.google.com/asset-inventory/docs/searching-resources). Kinds that use Pub/Sub or Resource Manager for `RESOURCE` (topics, subscriptions, projects, folders, organizations) reject `assetQuery`. |
| `IAM_POLICY` | `listAssets`, or `searchAllIamPolicies` when `assetQuery` is set | `iam_policy` | Yes. [IAM policy search syntax](https://cloud.google.com/asset-inventory/docs/searching-iam-policies). Example: `memberTypes:serviceAccount`. |
| `ORG_POLICY` | `listAssets` | `org_policy` (a list; one resource can have several constraints) | No. Config validation fails if `assetQuery` is set. |
| `ACCESS_POLICY` | `listAssets` | `access_policy`, `access_level`, or `service_perimeter` | No. Config validation fails if `assetQuery` is set. |
| `OS_INVENTORY` | `listAssets` | `os_inventory` | No. Config validation fails if `assetQuery` is set. |
| `RELATIONSHIP` | `listAssets` | `related_asset` | No. Config validation fails if `assetQuery` is set. |

`selector.assetQuery` is the Cloud Asset API query. `selector.query` stays the JQ filter applied after the integration returns data. `listAssets` has no query parameter, so `assetQuery` is rejected for `ORG_POLICY`, `ACCESS_POLICY`, `OS_INVENTORY`, and `RELATIONSHIP` instead of being ignored.

Non-`RESOURCE` records are explicit inventory, not Policy Analyzer effective or inherited access. Project asset types are read once per accessible project. `cloudresourcemanager.googleapis.com/Folder` and `cloudresourcemanager.googleapis.com/Organization` are read on those folder and organization scopes.

Use `itemsToParse` to expand a repeated block such as `.iam_policy.bindings` or `.org_policy`. `itemsToParse` walks one array, so an IAM binding's `members` array stays on the entity.

`searchAllResources` and `searchAllIamPolicies` default to 400 requests per minute per consumer project. `listAssets` defaults to 100 requests per minute per consumer project, and also 800 per minute and 650,000 per day per organization. The integration rate-limits each API on its own quota and uses a page size of 1000 for `listAssets`.

Extra setup:

- `OS_INVENTORY` requires [VM Manager OS inventory](https://cloud.google.com/compute/docs/instances/os-inventory-management) to be collected for the VMs.
- `RELATIONSHIP` requires Security Command Center Premium or Enterprise. `listAssets` then returns each supported relationship for the asset type. An asset type with no relationships makes that request fail, and the kind resync fails instead of deleting entities.
- `ACCESS_POLICY` reads Access Context Manager access policies, access levels, and service perimeters.

Workload Identity, the `iam.gke.io/gcp-service-account` annotation from a Kubernetes service account to a Google service account, is not in these records.

```yaml
- kind: cloudresourcemanager.googleapis.com/Project
  selector:
    query: 'true'
    contentType: IAM_POLICY
    assetQuery: memberTypes:serviceAccount
  port:
    itemsToParse: .iam_policy.bindings
    entity:
      mappings:
        identifier: .name + "|" + .item.role + "|" + (.item.members | join(","))
        title: .item.role
        blueprint: '"gcpIamPolicyBinding"'
        properties:
          role: .item.role
          members: .item.members
          resource: .name
          assetType: .asset_type
        relations:
          project: .__project.name
```

`contentType: IAM_POLICY` on `cloudresourcemanager.googleapis.com/Project` is the allow policy attached to the project. The same content type on `iam.googleapis.com/ServiceAccount` is the allow policy attached to that service account. `assetQuery: memberTypes:serviceAccount` keeps Google service account principals. Project-scoped assets include `__project`. Folder-scoped assets include `__folder`, and organization-scoped assets include `__organization`.

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

Real-time feeds stay on `--content-type=resource`. A live event updates mappings whose `contentType` is `RESOURCE` (the default). Mappings with any other `contentType` ignore the event and stay on the resync schedule. The integration does not apply IAM policy, organization policy, access policy, OS inventory, or relationship feed payloads.

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