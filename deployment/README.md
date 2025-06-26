# Ocean Deployment Examples

This directory contains example Terraform implementations demonstrating how Ocean integrations can be deployed across different cloud providers. These examples serve as reference implementations and learning resources.

## ⚠️ Important Note

These examples are provided to demonstrate deployment patterns. For production deployments, we recommend using our dedicated cloud provider installation:

- [AWS Ocean Integration](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/aws/installations/installation)
- [GCP Ocean Integration](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/gcp/installation)
- [Azure Ocean Integration](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/cloud-providers/azure/installation)

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

For production deployments, please use the dedicated cloud provider installations mentioned above.

## Contributing

If you're interested in contributing to Ocean's deployment infrastructure:
- For cloud provider integrations (AWS, GCP, Azure), contribute to their dedicated repositories
- For example improvements or documentation, contributions to this directory are welcome

## License

This code is part of the Ocean project and is licensed under the same terms as the main repository.
