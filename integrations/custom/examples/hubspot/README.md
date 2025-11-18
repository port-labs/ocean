# HubSpot Integration for Port Ocean

Integrate your HubSpot CRM with Port to track contacts, companies, deals, and feature requests directly in your internal developer portal.

## Overview

This integration syncs data from HubSpot CRM to Port, creating entities for:

- 👤 **Ocean HubSpot Contacts** - CRM contacts with email and properties
- 🏢 **Ocean HubSpot Companies** - Organizations and accounts
- 💼 **Ocean HubSpot Deals** - Sales opportunities with pipeline stages
- 🚀 **Ocean HubSpot Feature Requests** - Custom object for product roadmap management

## Quick Start

### 1. Get Your HubSpot API Key

1. Log in to your HubSpot account
2. Go to **Settings** → **Integrations** → **Private Apps**
3. Create a new private app or use an existing one
4. Copy your **Access Token** (keep it secure!)

Required Scopes:
- `crm.objects.contacts.read`
- `crm.objects.companies.read`
- `crm.objects.deals.read`
- `crm.schemas.custom.read` (for custom objects)

### 2. Install with One Command

```bash
helm install port-ocean-hubspot port-labs/port-ocean \
  --set port.clientId=<YOUR_PORT_CLIENT_ID> \
  --set port.clientSecret=<YOUR_PORT_CLIENT_SECRET> \
  --set integration.identifier=hubspot-integration \
  --set integration.type=custom \
  --set integration.version=0.1.0-dev \
  --set integration.config.baseUrl=https://api.hubapi.com \
  --set integration.config.authType=bearer \
  --set integration.secrets.token=<YOUR_HUBSPOT_ACCESS_TOKEN> \
  --set initializePortResources=true \
  --set sendRawDataExamples=true
```

### 3. Verify It's Running

```bash
kubectl logs -l app.kubernetes.io/instance=port-ocean-hubspot --follow
```

## What Gets Synced

### Contacts
- Name and email
- Create and update dates
- Custom properties
- Lifecycle stage

### Companies
- Company name and domain
- Create and update dates
- Custom properties
- Industry information

### Deals
- Deal name and amount
- Pipeline and stage
- Close date and probability
- Owner information
- Associated contacts and companies

### Feature Requests (Custom Object)
- Title and description
- Status (open, planned, in progress, complete)
- Vote count
- Promised ETA and team
- Product roadmap URL
- Customer commitment level

## Use Cases

- **Sales Pipeline Visibility**: Track deals and their stages in your developer portal
- **Customer Context**: See which contacts and companies are associated with features
- **Product Roadmap**: Manage feature requests with voting and prioritization
- **Stakeholder Updates**: Generate reports on pipeline health and feature progress
- **Engineering Alignment**: Connect customer requests to engineering initiatives

## Files Included

- `blueprints.json` - Port blueprint definitions for HubSpot entities
- `port-app-config.yml` - Data mapping configuration
- `installation.md` - Detailed installation instructions
- `README.md` - This file

## Configuration

The integration connects to HubSpot's API at `https://api.hubapi.com` and uses:

- **Authentication**: Bearer Token (Private App Access Token)
- **Method**: HTTP GET
- **Pagination**: `after` cursor-based (limit up to 100 per request)

### Main Endpoints Used

- `/crm/v3/objects/contacts` - Fetch all contacts
- `/crm/v3/objects/companies` - Fetch companies
- `/crm/v3/objects/deals` - Fetch sales deals
- `/crm/v3/objects/2-24903472` - Fetch feature requests (custom object)
- `/crm/v3/pipelines/deals` - Fetch deal pipelines and stages

## Customization

To customize the data mapping:

1. Edit `port-app-config.yml` to adjust entity mappings
2. Modify blueprints in `blueprints.json` to add custom properties
3. Add more custom objects by finding their objectTypeId from `/crm/v3/schemas`
4. Update the Helm installation to reference your custom config

## Troubleshooting

**No data appearing?**
- Verify your HubSpot access token is correct
- Check that required scopes are enabled
- Ensure blueprints are created in Port
- Review logs: `kubectl logs -l app.kubernetes.io/instance=port-ocean-hubspot`

**Authentication errors?**
- Regenerate your access token
- Verify the token has the correct scopes
- Check token hasn't expired

**Missing custom objects?**
- Find the objectTypeId using: `GET /crm/v3/schemas`
- Update `port-app-config.yml` with the correct objectTypeId
- Ensure your token has `crm.schemas.custom.read` scope

## Example Queries in Port

Once data is synced, you can run queries like:

- **Top Deals**: Filter by amount and stage
- **Feature Requests by Votes**: Sort by vote count
- **Companies with Open Deals**: View active pipeline
- **Contacts by Lifecycle Stage**: Segment your CRM data

## Resources

- [HubSpot API Documentation](https://developers.hubspot.com/docs/api/overview)
- [HubSpot CRM API](https://developers.hubspot.com/docs/api/crm/understanding-the-crm)
- [Port Ocean Documentation](https://docs.getport.io)
- [Ocean Custom Integration Guide](https://docs.getport.io/build-your-software-catalog/custom-integration/custom)

## Support

Need help?
- Port Support: support@getport.io
- HubSpot Developer Support: developers.hubspot.com/community

---

**Note**: This integration requires Port Ocean's Ocean Custom integration. Ensure you're using version `0.1.0-dev` or later.




