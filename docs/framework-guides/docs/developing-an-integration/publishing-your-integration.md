---
title: Publishing Your Integration
sidebar_label: 📦 Publishing Your Integration
sidebar_position: 8
---

# 📦 Publishing Your Integration

With your integration developed and tested, you have several options for deployment. You can deploy it directly using [Helm](../deployment/helm.md), [Terraform](../deployment/terraform.md), [Docker](../deployment/docker.md), or [Argo CD](../deployment/argocd.md). However, if you want to make your integration available to other Port users, you'll need to publish it to the Ocean repository. This guide will walk you through the process of publishing your integration.

## Prerequisites

- Ensure you have a `.port` folder with a `spec.yaml` file that holds information about the integration, configuration, features, and type.
- Ensure you have a `pyproject.toml` file that holds information about the integration, including version, dependencies, and other metadata.
- Your integration should pass the following linting checks using the `make lint` command:
  - `black` for code formatting.
  - `mypy` for type checking.
  - `ruff` for code quality analysis.
  - `poetry check` for dependency checks.

:::note
All of the integrations powered by Ocean are expected to pass the automated CI check, when you open a PR to the [Ocean repository](https://github.com/port-labs/ocean) in Github, Port's CI will validate that your new code passes the CI checks and Port's team will only merge your code once it passes.
:::

## Publishing Process

### For Developers Contributing to an Existing Integration

If you've already cloned and developed your changes to an existing integration within the Ocean repository, the process is straightforward:

1. Create a changelog for your changes
2. Bump the version in your `pyproject.toml` file
3. Commit your changes to a new branch
4. Push your branch and create a pull request

The CI will automatically validate your changes, and once approved, your changes will be published to the Ocean repository.

### For Contributors Creating a New Integration

If you're publishing your integration for the first time, follow these steps:

#### Forking and Cloning

Start by forking the Ocean repository to your GitHub account. This creates a personal copy where you can make changes. Clone your fork to your local machine using:

```bash showLineNumbers
git clone https://github.com/your-username/ocean.git
```

#### Adding Your Integration

Place your integration code inside the `integrations` folder of your local repository. Follow the same file hierarchy structure used by other public integrations to maintain consistency. After adding your code, run `make lint` to ensure it meets all quality standards.

#### Creating a Changelog

A changelog is essential for tracking and communicating changes to your integration. It provides users with a clear history of updates and improvements. To create a changelog, run the following command:

```console showLineNumbers title="bash"
$ poetry run towncrier create --content "Implemented Port integration for Jira" 0.1.0-beta.feature.md
```

This command creates a new file in the `changelog` directory. Next, build the changelog by running:

<details>
<summary><b>Building the Changelog</b></summary>

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

#### Documentation

To make your integration accessible to other users, you need to provide clear documentation. Fork the [Port Docs repository](https://github.com/port-labs/port-docs) and add your integration documentation following the established format used by other integrations. Your documentation should include:

- Installation instructions
- Configuration options
- Usage examples
- Troubleshooting guides
- API references

#### Submitting Your Integration

Commit your changes and push them to your fork. Then, open a pull request from your branch to the `main` branch of the Ocean repository. During the review process, collaborate with the community and maintainers to address any feedback and ensure your integration aligns with the framework's standards.

### Version Management

When updating your integration, remember to update the version number in the `pyproject.toml` file. This allows the CI to detect the new version and publish it to Port's image registry. 

## Conclusion

Publishing your integration to the Ocean repository makes it available to all Port users and contributes to the growing ecosystem of integrations. By following these steps and maintaining high-quality standards, you ensure that your integration becomes a valuable addition to the Port platform.

:::info Source Code
You can find the source code for the integration in the [Jira integration directory on GitHub](https://github.com/port-labs/ocean/tree/main/integrations/jira)
:::
