# gitlab-v2

An integration used to import gitlab-v2 resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/) *Replace this link with a link to this integration's documentation*

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)


### Description
- This integration pull data from gitlab using the gitlab api to your port account using the provided credentials in the
environment variable.
- It also include a webhook url which will be `{your base url}/integration/webhook`. This should be added to your gitlab
account webhook settings. Ensure you tick the necessary entitties you want to receive the webhook notification.
- The supported entities in the integrations are:
  - projects
  - groups
  - merge requests
  - issues


### Environment variables needed
 - OCEAN__PORT__CLIENT_ID (Gotten from your getport.io crdentials)
 - OCEAN__PORT__CLIENT_SECRET (Gotten from your getport.io crdentials)
 - OCEAN__PORT__BASE_URL (Port base url - "https://api.getport.io")
 - OCEAN__INTEGRATION__CONFIG__GITLAB_URL (Gitlab API base url https://gitlab.com/api/v4)
 - OCEAN__INTEGRATION__CONFIG__GITLAB_TOKEN (Gitlab personal access token)
 - OCEAN__INTEGRATION__CONFIG__GITLAB_SECRET (Gitlab webhook secret)
