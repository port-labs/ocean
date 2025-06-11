# Azure Devops

An integration used to import Azure Devops resources into Port.

## Features

### Recursive Group Member Expansion

When syncing team members, the integration supports optional recursive expansion of nested group structures. This allows you to discover all users within complex hierarchy trees like:

Azure DevOps Team → Azure DevOps Group → Entra (AAD) Group → User(s)

To enable this feature, set `expandNestedMembers: true` in your team selector configuration.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/git/azure-devops/)

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)
