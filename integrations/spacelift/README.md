# spacelift

An integration used to import spacelift resources into Port.

#### Install & use the integration - [Integration documentation](https://docs.port.io/build-your-software-catalog/sync-data-to-catalog/) *Replace this link with a link to this integration's documentation*

#### Develop & improve the integration - [Ocean integration development documentation](https://ocean.getport.io/develop-an-integration/)


# Environment Variables for Spacelift Integration

This file contains the required environment variables for the Spacelift integration. 

## Setup Instructions

1. Copy this content to a `.env` file in the same directory as `config.yaml`
2. Replace the placeholder values with your actual credentials and configuration

## Environment Variables Template

```bash
# Port API Configuration
OCEAN__PORT__PORT_CLIENT_ID=your_port_client_id_here
OCEAN__PORT__PORT_CLIENT_SECRET=your_port_client_secret_here

# Integration Configuration
OCEAN__PORT__INTEGRATION_IDENTIFIER=spacelift-integration

# Spacelift API Configuration
OCEAN__INTEGRATION__CONFIG__SPACELIFT_API_ENDPOINT=https://your-account.app.spacelift.io/graphql


OCEAN__INTEGRATION__CONFIG__SPACELIFT_API_KEY_ID=your_spacelift_api_key_id_here
OCEAN__INTEGRATION__CONFIG__SPACELIFT_API_KEY_SECRET=your_spacelift_api_key_secret_here

# Optional Configuration (uncomment and modify if needed)
# PAGE_SIZE=50
# MAX_RETRIES=3
```

## How to Get These Values

### Port API Credentials
1. Go to your Port application
2. Navigate to Settings > Credentials
3. Create a new client ID and secret or use existing ones

### Spacelift Configuration
1. **API Endpoint**: Replace `your-account` with your actual Spacelift account name
   - Format: `https://your-account.app.spacelift.io/graphql`
   
2. **API Key & Secret** 
   - Go to Spacelift Settings > API Keys
   - Create a new API key and note both the ID and secret

### Integration Identifier
- Choose a unique identifier for your integration instance
- Examples: `spacelift-prod`, `spacelift-dev`, `my-spacelift-integration`

## Usage

After creating your `.env` file with the above values, the integration will automatically load these environment variables when started.

**Note**: Make sure your `.env` file is in the same directory as `config.yaml` and that it's included in your `.gitignore` to avoid committing sensitive credentials to version control. 