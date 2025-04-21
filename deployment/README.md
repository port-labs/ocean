# Ocean Deployment

This directory contains Terraform modules for deploying Ocean integrations across different cloud providers.

## ⚠️ Important Note

This deployment code is the generic, integration-agnostic deployment framework for Ocean integrations. It can be used to deploy any Ocean integration to your cloud provider of choice.

For the three cloud provider integrations (AWS, GCP, and Azure), we maintain dedicated repositories that handle both the integration and the cloud infrastructure deployment:

- [AWS Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/aws_container_app)
- [GCP Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/azure_container_app_azure_integration)
- [Azure Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/gcp_cloud_run)

## Purpose

This code provides a generic deployment framework that can be used to deploy any Ocean integration. It's designed to be:
- Cloud-agnostic (supports AWS, GCP, and Azure)
- Integration-agnostic (can be used with any Ocean integration)
- Modular and reusable

## Structure

```
deployment/
└── terraform/
    ├── aws/          # AWS deployment modules
    ├── gcp/          # GCP deployment modules
    └── azure/        # Azure deployment modules
```

## Usage

This code is meant to be used when:
1. You're deploying a custom Ocean integration
2. You're deploying an integration that doesn't have a dedicated cloud provider repository
3. You need to deploy an integration to a cloud provider in a specific way

For the three cloud provider integrations (AWS, GCP, Azure), please use their dedicated repositories instead.

## Contributing

If you're interested in contributing to Ocean's deployment infrastructure:
- For cloud provider integrations (AWS, GCP, Azure), contribute to their dedicated repositories
- For generic integration deployment improvements, contribute to this directory

## License

This code is part of the Ocean project and is licensed under the same terms as the main repository.
