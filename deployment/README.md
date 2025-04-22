# Ocean Deployment Examples

This directory contains example Terraform implementations demonstrating how Ocean integrations can be deployed across different cloud providers. These examples serve as reference implementations and learning resources.

## ⚠️ Important Note

These examples are provided for educational purposes and to demonstrate deployment patterns. For production deployments, we recommend using our dedicated cloud provider repositories:

- [AWS Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/aws_container_app)
- [GCP Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/azure_container_app_azure_integration)
- [Azure Ocean Integration](https://github.com/port-labs/terraform-ocean-integration-factory/tree/main/examples/gcp_cloud_run)

## Purpose

These examples demonstrate:
- How to structure Terraform code for Ocean integrations
- Common deployment patterns across different cloud providers
- Integration configuration approaches

## Structure

```
deployment/
└── terraform/
    ├── aws/          # Example AWS deployment
    ├── gcp/          # Example GCP deployment
    └── azure/        # Example Azure deployment
```

## Usage

These examples are primarily intended for:
1. Learning how Ocean integrations can be deployed
2. Understanding common deployment patterns
3. Reference when building custom deployment solutions

For production deployments, please use the dedicated cloud provider repositories mentioned above.

## Contributing

If you're interested in contributing to Ocean's deployment infrastructure:
- For cloud provider integrations (AWS, GCP, Azure), contribute to their dedicated repositories
- For example improvements or documentation, contributions to this directory are welcome

## License

This code is part of the Ocean project and is licensed under the same terms as the main repository.
