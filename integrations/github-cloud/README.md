# GitHub Cloud Integration

A Port Ocean integration for importing GitHub Cloud resources into Port's software catalog. This integration enables real-time synchronization of GitHub repositories, pull requests, teams, and members.

## Features

- **Repository Management**: Sync repository metadata, including name, description, visibility, and creation date
- **Pull Request Tracking**: Monitor pull request status, reviews, and changes
- **Team Management**: Sync team structures and member associations
- **Member Management**: Track organization members and their roles
- **Webhook Support**: Real-time updates via GitHub webhooks
- **Resync Capabilities**: Full resync of all resources on demand

## Installation

### Using Port's UI
1. Navigate to your Port instance
2. Go to Integrations > Create Integration
3. Select GitHub Cloud from the available integrations
4. Follow the setup wizard to configure your GitHub credentials

### Manual Installation
1. Clone this repository
2. Install dependencies:
   ```bash
   make install
   ```
3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your GitHub credentials
   ```
4. Run the integration:
   ```bash
   make run
   ```

## Development

### Prerequisites
- Python 3.11+
- Poetry for dependency management
- GitHub account with appropriate permissions

### Setup Development Environment
1. Create a virtual environment:
   ```bash
   make venv
   ```
2. Install development dependencies:
   ```bash
   make install-dev
   ```
3. Run tests:
   ```bash
   make test
   ```

### Project Structure
- `github_cloud/`: Main package directory
  - `clients/`: GitHub API client implementations
  - `webhook/`: Webhook processing logic
  - `helpers/`: Utility functions and constants
- `tests/`: Test suite
- `main.py`: Integration entry point

### Adding New Features
1. Create a new branch for your feature
2. Add tests in the `tests/` directory
3. Implement the feature
4. Run tests and linting:
   ```bash
   make test
   make lint
   ```
5. Submit a pull request

## Documentation

- [Integration Documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/)
- [Ocean Integration Development Guide](https://ocean.getport.io/develop-an-integration/)

## Contributing

Please read [CONTRIBUTING.md](CONTRIBUTING.md) for details on our code of conduct and the process for submitting pull requests.

## License

This project is licensed under the MIT License - see the LICENSE file for details.
