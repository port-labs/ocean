---
sidebar_position: 8
---


# 📦 Publishing Your Integration
With the integration developed, you can decide to deploy it via [Helm](../deployment/helm.md), [Terraform](../deployment/terraform.md), [Docker](../deployment//docker.md), or [ArgoCD](../deployment/argocd.md).

However, if you would like your integration to be available to other users on Port, you can publish it to the Port Ocean repository. This will make it available to other users who can install it directly from the Port Ocean dashboard.

In this guide, we will learn how to publish your integration to the Port Ocean repository.


## Creating a Changelog
Before you publish your integration, you need to create a changelog. A changelog is a file that contains a curated, chronologically ordered list of notable changes for each version of a project. This file is used to keep track of changes to the project and to communicate these changes to users.

Run the following command to create a changelog draft:

```console showLineNumbers title="bash"
$ poetry run towncrier create --content "Implemented Port integration for Jira" 0.1.0-beta.feature.md
```

This command will create a new file named `0.1.0-beta.feature.md` in the `changelog` directory.

Next, let's add this to the `CHANGELOG.md` file. Run the following command:

<details>

<summary><b>Adding the changelog to the CHANGELOG.md file (Click to expand)</b></summary>

```console showLineNumbers title="bash"
$ poetry run towncrier build --yes --version 0.1.0-beta
Loading template...
Finding news fragments...
Rendering news fragments...
Writing to newsfile...
Staging newsfile...
Removing the following files:
/home/lordsarcastic/Code/port/ocean/integrations/jira/changelog/0.1.0-beta.feature.md
```

</details>

Commit the changes to git and push them to your repository. The next step is to create a pull request to the Port Ocean repository.

## Documenting Your Integration
To make your integration available to other users, you also need to document it. This documentation will be used to provide information about the integration to users who want to install it.

You can do this by forking the [Port Docs repository](https://github.com/port-labs/port-docs) and adding your integration documentation, following the same format used by other integrations.

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)

:::

## Next Steps
With your integration published, you can now share it with other users on Port. You can also continue to improve your integration by adding more features and fixing bugs.
