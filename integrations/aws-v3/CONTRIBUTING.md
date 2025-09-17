# Contributing to AWS-v3 Integration

Thank you for your interest in contributing to the AWS-v3 integration! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.12+
- Poetry (for dependency management)
- AWS CLI configured with appropriate permissions
- Git

### Development Setup

1. **Fork and Clone**
   ```bash
   git clone https://github.com/your-username/ocean.git
   cd ocean/integrations/aws-v3
   ```

2. **Install Dependencies**
   ```bash
   make install
   ```

3. **Set Up AWS Credentials**
   ```bash
   export OCEAN__INTEGRATION__CONFIG__AWS_ACCESS_KEY_ID="your_key"
   export OCEAN__INTEGRATION__CONFIG__AWS_SECRET_ACCESS_KEY="your_secret"
   or use assume role
   export OCEAN__INTEGRATION__CONFIG__AWS_ASSUME_ROLE_ARN="your_role_arn"
   ```

4. **Run Tests**
   ```bash
   make test
   ```


## Adding New Resource Kinds

### Quick Start

1. **Follow the Guide**: Use [ADDING_NEW_KINDS.md](./ADDING_NEW_KINDS.md) for step-by-step instructions
2. **Study Examples**: Look at existing implementations (S3, ECS, EC2)
3. **Test Thoroughly**: Ensure your implementation works with real AWS resources
4. **Update Documentation**: Add your resource to relevant documentation

### Resource Kind Checklist

- [ ] Added to `ObjectKind` enum in `types.py`
- [ ] Created models in `aws/core/exporters/{service}/{resource}/models.py`
- [ ] Implemented actions in `aws/core/exporters/{service}/{resource}/actions.py`
- [ ] Created exporter in `aws/core/exporters/{service}/{resource}/exporter.py`
- [ ] Added resync handler in `main.py`
- [ ] Updated `.port/spec.yaml`
- [ ] Added package `__init__.py`
- [ ] Added to `.port/resources/blueprints.json`
- [ ] Added to `.port/resources/port-app-config.yml`
- [ ] Written comprehensive tests
- [ ] Tested with real AWS resources
- [ ] Updated documentation

## Code Standards

### Python Style

We follow Python best practices and use several tools for code quality:

```bash
make lint
```

### Code Organization

```
aws-v3/
├── aws/
│   ├── core/
│   │   ├── exporters/
│   │   │   ├── {service}/
│   │   │   │   ├── {resource}/
│   │   │   │   │   ├── models.py
│   │   │   │   │   ├── actions.py
│   │   │   │   │   └── exporter.py
│   │   │   │   └── __init__.py
│   │   │   └── ...
│   │   └── ...
│   └── ...
├── tests/
├── main.py
├── integration.py
└── .port/
    └── spec.yaml
```
