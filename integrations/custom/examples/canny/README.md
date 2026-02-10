# Canny Integration for Port Ocean

Integrate your Canny feedback board with Port to track feature requests, manage priorities, and understand customer feedback directly in your internal developer portal.

## Overview

This integration syncs data from Canny (feedback management platform) to Port, creating entities for:

- 📋 **Ocean Canny Boards** - Your Canny feedback boards
- 📝 **Ocean Canny Posts** - Feature requests and feedback
- 🏷️ **Ocean Canny Categories** - Board categories for organization
- 🏢 **Ocean Canny Companies** - Customer organizations
- ⭐ **Ocean Canny Votes** - Individual user votes on posts

## Quick Start

### 1. Get Your Canny API Key

Navigate to Canny Settings → API & Webhooks → copy your API Key

### 2. Install with One Command

```bash
helm install port-ocean-canny port-labs/port-ocean \
  --set port.clientId=<YOUR_PORT_CLIENT_ID> \
  --set port.clientSecret=<YOUR_PORT_CLIENT_SECRET> \
  --set integration.identifier=canny-integration \
  --set integration.type=custom \
  --set integration.version=0.1.0-dev \
  --set 'integration.config.baseUrl=https://canny.io/api/v1?apiKey=<YOUR_CANNY_API_KEY>' \
  --set integration.config.authType=none \
  --set initializePortResources=true \
  --set sendRawDataExamples=true
```

**Note**: Canny uses non-standard authentication (API key in request body). We work around this by embedding the API key in the base URL as a query parameter.

### 3. Verify It's Running

```bash
kubectl logs -l app.kubernetes.io/instance=port-ocean-canny --follow
```

## What Gets Synced

### Canny Boards
- Board name and URL
- Post count
- Privacy settings
- Creation date

### Feature Requests (Posts)
- Title and description
- Status (open, planned, in progress, complete, closed)
- Vote count and score
- Author information
- Tags and categories
- ETA and owner

### Categories
- Category name and URL
- Post count
- Associated board

### Companies
- Company name
- Custom fields
- Monthly spend
- Creation date

### Votes
- Voter information (name and email)
- Related post
- Vote timestamp

## Use Cases

- **Product Roadmap Planning**: Track feature requests by vote count and status
- **Customer Success**: Monitor feedback from specific companies
- **Engineering Prioritization**: See which features are most requested
- **Stakeholder Updates**: Generate reports on planned vs completed features

## Files Included

- `blueprints.json` - Port blueprint definitions for Canny entities
- `port-app-config.yml` - Data mapping configuration
- `installation.md` - Detailed installation instructions
- `README.md` - This file

## Configuration

The integration connects to Canny's API at `https://canny.io/api/v1` and uses:

- **Authentication**: API Key (in request body)
- **Method**: HTTP POST
- **Pagination**: limit/skip (up to 100 per request)

### Main Endpoints Used

- `/boards/list` - Fetch all boards
- `/categories/list` - Fetch categories
- `/posts/list` - Fetch feature requests
- `/companies/list` - Fetch customer companies

## Customization

To customize the data mapping:

1. Edit `port-app-config.yml` to adjust entity mappings
2. Modify blueprints in `blueprints.json` to add custom properties
3. Update the Helm installation to reference your custom config

## Troubleshooting

**No data appearing?**
- Verify your Canny API key is correct
- Check that blueprints are created in Port
- Review logs: `kubectl logs -l app.kubernetes.io/instance=port-ocean-canny`

**Rate limiting issues?**
- Canny has API rate limits
- Consider reducing sync frequency
- Contact Canny support for higher limits

## Example Queries in Port

Once data is synced, you can run queries like:

- **Top Requested Features**: Filter posts by vote count
- **Features by Status**: Group posts by status (open, planned, etc.)
- **Customer Feedback**: View posts related to specific companies
- **Board Health**: Analyze post count and engagement per board

## Resources

- [Canny API Documentation](https://developers.canny.io/api-reference)
- [Port Ocean Documentation](https://docs.getport.io)
- [Ocean Custom Integration Guide](https://docs.getport.io/build-your-software-catalog/custom-integration/custom)

## Support

Need help?
- Port Support: support@getport.io
- Canny API Issues: help@canny.io

---

**Note**: This integration requires Port Ocean's Ocean Custom integration. Ensure you're using version `0.1.0-dev` or later.

