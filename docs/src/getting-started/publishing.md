# Publishing an Integration

This guide outlines the steps to publish an integration for the Ocean framework. Integrations allow you to extend the functionality of the Ocean framework with custom features and capabilities.

## Prerequisites

- Ensure you have a `.port` folder with a `spec.yaml` file that holds information about the integration, including version, configuration, features, and type.
- Your integration should pass the following linting checks using `make lint` command:
    - `black` for code formatting.
    - `mypy` for type checking.
    - `ruff` for code quality analysis.
    - `poetry check` for dependency checks.
    - `poetry lock` to update the `pyproject.toml` file.

## Steps to Publish an Integration

1. **Create a Fork**

    Fork the Ocean framework repository to your GitHub account. This will create a copy of the repository under your account.

2. **Clone Your Fork**

    Clone the forked repository to your local machine using the following command:
     ```
     git clone https://github.com/your-username/ocean-framework.git
     ```

3. **Add Your Integration**
   
    Place your integration code inside the `integrations` folder of your local repository. Ensure the file hierarchy matches that of other public integrations.
    <details markdown="1">
    <summary>Scaffolding the project with <code>make new</code></summary>
   
    You may use the <code>make new</code> command instead of <code>ocean new</code> to scaffold a new integration project in the integrations folder.

    The make command will use the ocean new command behind the scenes.
    </details>

4. **Run Linting and Checks**

    Run `make lint` to ensure your integration meets quality standards:

5. **Commit and Push**

    Commit your changes to the branch and push the changes to your fork on GitHub.

6. **Open a Pull Request**

    Open a pull request from your branch in your fork to the `main` branch of the original Ocean framework repository.

7. **Review and Collaboration**

    Collaborate with the community and maintainers to address any feedback on your pull request. Make necessary changes to ensure your integration aligns with the framework's standards.

8. **Merge and Publish**

    Once your pull request is approved and passes all checks, it will be merged into the main repository. Your integration will now be available to all users of the Ocean framework.

## Publishing a New Version

When merging a new version of your integration, ensure that the version number in the `spec.yaml` file is updated. This will allow the CI to detect the new version and publish it to port image registry. 

## Conclusion

Publishing an integration for the Ocean framework allows you to contribute your custom features and functionalities to the framework's ecosystem. Following the steps outlined in this guide ensures that your integration meets the framework's quality standards and becomes a valuable addition to the community.