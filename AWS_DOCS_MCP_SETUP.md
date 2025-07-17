# 🚀 AWS Documentation MCP - Team Setup

This setup provides your team with seamless access to AWS documentation directly within Cursor, making AWS development faster and more accurate.

## Quick Start

### 1. One-Command Setup
```bash
./scripts/setup-aws-docs-mcp.sh
```

That's it! The script will:
- ✅ Install all prerequisites (`uv`, Python 3.10+)
- ✅ Install the AWS Documentation MCP Server
- ✅ Configure Cursor automatically
- ✅ Set up cursor rules for best practices
- ✅ Create team documentation

### 2. Restart Cursor
After running the script, **restart Cursor completely** to load the new MCP configuration.

### 3. Start Using AWS Docs
You can now use AWS documentation directly in Cursor chat:

```
@aws-docs How do I configure S3 bucket policies for cross-account access?
@aws-docs Show me Lambda function configuration best practices
@aws-docs Find documentation about VPC endpoint setup
```

## What This Gives Your Team

### 🔍 **Real-time AWS Documentation Access**
- Search across all AWS documentation
- Get specific page content in markdown format
- Discover related AWS services and best practices
- Always get the most current information

### 📚 **Intelligent Recommendations**
- Find complementary AWS services
- Discover architecture patterns
- Get troubleshooting guides
- Access pricing and limits information

### ✅ **Built-in Best Practices**
- Automatic source citation
- Current AWS best practices
- Integration with Ocean development patterns
- Team-consistent AWS usage guidelines

## Development Workflow Integration

### For Ocean Integrations
When working on AWS-related integrations:

1. **Research First**: Use MCP to understand AWS service capabilities
2. **Verify Configurations**: Get official AWS configuration examples
3. **Check Permissions**: Find exact IAM permissions needed
4. **Cite Sources**: All AWS information includes proper citations

### Example Usage Scenarios

#### Setting up S3 Integration
```
User: "I need to implement S3 event notifications for our Ocean integration"
Assistant: [Uses MCP to fetch latest S3 event documentation]
Result: Current S3 event configuration with exact JSON examples and IAM permissions
```

#### Configuring AWS Lambda
```
User: "What are the Lambda timeout and memory best practices for high-throughput processing?"
Assistant: [Uses MCP to get Lambda configuration documentation]
Result: Official AWS recommendations with specific configuration examples
```

#### VPC Setup
```
User: "How do I configure VPC endpoints for private S3 access?"
Assistant: [Uses MCP to get VPC endpoint documentation]
Result: Step-by-step VPC endpoint setup with security considerations
```

## Troubleshooting

### MCP Not Working?
1. **Restart Cursor** completely
2. **Check installation**: Run `uvx list` to verify MCP server is installed
3. **Re-run setup**: `./scripts/setup-aws-docs-mcp.sh`
4. **Check logs**: Look at Cursor's developer tools for MCP errors

### For China Regions
If you need to access AWS China documentation, edit the MCP configuration:
```json
"AWS_DOCUMENTATION_PARTITION": "aws-cn"
```

### Manual Configuration
If you need to manually configure MCP, check the configuration file location:
- **All platforms**: `~/.cursor/mcp.json`

## Team Benefits

### 🎯 **Consistency**
- All team members get the same AWS information
- Reduces configuration drift between environments
- Ensures everyone follows current AWS best practices

### ⚡ **Speed**
- No more switching to browser for AWS docs
- Instant access to configuration examples
- Quick discovery of related AWS services

### 🔒 **Accuracy**
- Always current AWS documentation
- Official AWS examples and configurations
- Proper citation of all sources

### 🤝 **Collaboration**
- Shared understanding of AWS services
- Consistent AWS terminology across team
- Easy sharing of AWS configuration examples

## Advanced Usage

### Custom Queries
The MCP responds well to specific, contextual queries:

```
# Instead of: "S3 setup"
# Use: "I'm configuring S3 for storing integration logs with 90-day retention. Get documentation for lifecycle policies and cross-region replication."

# Instead of: "Lambda memory"
# Use: "Setting up Lambda for processing Ocean webhook data with 10MB payloads. Find memory and timeout configuration recommendations."
```

### Integration with Existing Rules
This MCP setup integrates with your existing cursor rules:
- `core-development.mdc` - For Ocean platform development
- `integration-development.mdc` - For building integrations
- `python-fast-api.mdc` - For Python/FastAPI specific patterns
- `aws-documentation-mcp.mdc` - For AWS documentation usage (new)

## Support

- **Setup Issues**: Re-run `./scripts/setup-aws-docs-mcp.sh`
- **Usage Questions**: Check the generated `AWS_DOCS_MCP_SETUP.md` file
- **Team Guidelines**: See `.cursor/rules/aws-documentation-mcp.mdc`


## What was installed

✅ **AWS Documentation MCP Server** - Provides access to AWS documentation within Cursor
✅ **Cursor MCP Configuration** - Automatically configured for team use
✅ **Cursor Rules** - Added AWS documentation best practices

### Available Commands
- **Read Documentation**: Fetch specific AWS docs pages
- **Search Documentation**: Search across all AWS documentation
- **Get Recommendations**: Find related AWS documentation
- **Cite Sources**: All responses include proper citations

### For China regions:
Edit the MCP configuration file and change:
```json
"AWS_DOCUMENTATION_PARTITION": "aws-cn"
```
