# Wiz

An integration used to import Wiz resources into Port. The integration allows you to import `projects`, `issues`, `controls`, and `serviceTickets` from your Wiz account into Port, according to your mapping and definitions.

### Prerequisites
Your Wiz credentials should have the `read:projects` and `read:issues` permission scopes. Visit the Wiz [documentation](https://integrate.wiz.io/reference/prerequisites) for a guide on how to get your credentials as well as set permissions.

### Notes

1. The `wizApiUrl` and `wizTokenUrl` must be set since they do not have default value as there are at least 2 possible URLs a client will have based on their location.

### Resources
1. Install & use the integration - [Integration documentation](https://docs.getport.io/build-your-software-catalog/sync-data-to-catalog/code-quality-security/wiz) 
2. Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
