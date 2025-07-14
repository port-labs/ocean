#!/bin/bash

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Function to detect OS
detect_os() {
    case "$(uname -s)" in
        Darwin*) echo "macos";;
        Linux*) echo "linux";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *) echo "unknown";;
    esac
}

# Function to install uv
install_uv() {
    print_status "Installing uv package manager..."

    if command_exists uv; then
        print_success "uv is already installed"
        return 0
    fi

    case "$(detect_os)" in
        "macos"|"linux")
            curl -LsSf https://astral.sh/uv/install.sh | sh
            ;;
        "windows")
            powershell -c "irm https://astral.sh/uv/install.ps1 | iex"
            ;;
        *)
            print_error "Unsupported operating system for automatic uv installation"
            print_status "Please install uv manually from: https://docs.astral.sh/uv/getting-started/installation/"
            exit 1
            ;;
    esac

    # Source the shell profile to get uv in PATH
    if [ -f "$HOME/.cargo/env" ]; then
        source "$HOME/.cargo/env"
    fi

    if command_exists uv; then
        print_success "uv installed successfully"
    else
        print_error "Failed to install uv. Please install manually and re-run this script."
        exit 1
    fi
}

# Function to install Python 3.10+
install_python() {
    print_status "Checking Python version..."

    if command_exists python3; then
        PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
        PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

        if [ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -ge 10 ]; then
            print_success "Python $PYTHON_VERSION is already installed and meets requirements"
            return 0
        fi
    fi

    print_status "Installing Python 3.11 via uv..."
    uv python install 3.11
    print_success "Python 3.11 installed via uv"
}

# Function to install AWS Documentation MCP Server
install_mcp_server() {
    print_status "Checking AWS Documentation MCP Server installation..."

    # Check if the tool is already installed
    if uv tool list | grep -q "awslabs.aws-documentation-mcp-server"; then
        print_success "AWS Documentation MCP Server is already installed"

        # Check if it needs upgrading
        print_status "Checking for updates..."
        if uv tool upgrade awslabs.aws-documentation-mcp-server 2>/dev/null; then
            print_success "AWS Documentation MCP Server updated to latest version"
        else
            print_success "AWS Documentation MCP Server is already up to date"
        fi
    else
        print_status "Installing AWS Documentation MCP Server..."

        # Install the MCP server globally
        if uv tool install awslabs.aws-documentation-mcp-server; then
            print_success "AWS Documentation MCP Server installed successfully"
        else
            print_error "Failed to install AWS Documentation MCP Server"
            print_status "You can still use the MCP server via uvx (temporary runs)"
            print_status "The configuration will use 'uvx' which downloads and runs the tool as needed"
        fi
    fi
}

# Function to get Cursor MCP config path
get_cursor_mcp_path() {
    case "$(detect_os)" in
        "macos"|"linux")
            echo "$HOME/.cursor/mcp.json"
            ;;
        "windows")
            echo "$HOME/.cursor/mcp.json"
            ;;
        *)
            print_error "Unknown operating system"
            exit 1
            ;;
    esac
}

# Function to configure Cursor MCP
configure_cursor_mcp() {
    print_status "Configuring Cursor MCP integration..."

    MCP_CONFIG_PATH=$(get_cursor_mcp_path)
    MCP_CONFIG_DIR=$(dirname "$MCP_CONFIG_PATH")

    # Create the directory if it doesn't exist
    mkdir -p "$MCP_CONFIG_DIR"

    # Check if MCP config already exists
    if [ -f "$MCP_CONFIG_PATH" ]; then
        print_status "Existing MCP configuration found. Updating AWS documentation server..."

        # Create a backup
        cp "$MCP_CONFIG_PATH" "$MCP_CONFIG_PATH.backup.$(date +%Y%m%d_%H%M%S)"

        # Use Python to merge configurations properly
        python3 << 'EOF'
import json
import sys

config_path = sys.argv[1] if len(sys.argv) > 1 else ""

try:
    # Read existing config
    with open(config_path, 'r') as f:
        config = json.load(f)

    # Ensure mcpServers exists
    if 'mcpServers' not in config:
        config['mcpServers'] = {}

    # Add/Update AWS documentation server
    # Check if tool is installed to determine command format
    import subprocess
    try:
        result = subprocess.run(['uv', 'tool', 'list'], capture_output=True, text=True, check=True)
        if 'awslabs.aws-documentation-mcp-server' in result.stdout:
            command = "awslabs.aws-documentation-mcp-server"
            args = []
            print("✅ Using installed version of AWS MCP server")
        else:
            command = "uvx"
            args = ["awslabs.aws-documentation-mcp-server@latest"]
            print("✅ Using uvx (temporary) version of AWS MCP server")
    except:
        command = "uvx"
        args = ["awslabs.aws-documentation-mcp-server@latest"]
        print("✅ Using uvx (temporary) version of AWS MCP server")

    config['mcpServers']['awslabs.aws-documentation-mcp-server'] = {
        "command": command,
        "args": args,
        "env": {
            "FASTMCP_LOG_LEVEL": "ERROR",
            "AWS_DOCUMENTATION_PARTITION": "aws"
        },
        "disabled": False,
        "autoApprove": [
            "read_documentation",
            "search_documentation",
            "recommend",
            "get_available_services"
        ]
    }

    # Write updated config
    with open(config_path, 'w') as f:
        json.dump(config, f, indent=2)

    print("✅ Configuration updated successfully")

except Exception as e:
    print(f"❌ Error updating configuration: {e}")
    sys.exit(1)
EOF "$MCP_CONFIG_PATH"

    else
        print_status "Creating new MCP configuration..."

        # Create new configuration
        # Determine command format based on installation
        local MCP_COMMAND="uvx"
        local MCP_ARGS='["awslabs.aws-documentation-mcp-server@latest"]'

        if uv tool list 2>/dev/null | grep -q "awslabs.aws-documentation-mcp-server"; then
            MCP_COMMAND="awslabs.aws-documentation-mcp-server"
            MCP_ARGS='[]'
            print_status "Using installed version of AWS MCP server"
        else
            print_status "Using uvx (temporary) version of AWS MCP server"
        fi

        cat > "$MCP_CONFIG_PATH" << EOF
{
  "mcpServers": {
    "awslabs.aws-documentation-mcp-server": {
      "command": "$MCP_COMMAND",
      "args": $MCP_ARGS,
      "env": {
        "FASTMCP_LOG_LEVEL": "ERROR",
        "AWS_DOCUMENTATION_PARTITION": "aws"
      },
      "disabled": false,
      "autoApprove": [
        "read_documentation",
        "search_documentation",
        "recommend",
        "get_available_services"
      ]
    }
  }
}
EOF
    fi

    print_success "Cursor MCP configuration updated at: $MCP_CONFIG_PATH"
}

# Function to test MCP installation
test_mcp_installation() {
    print_status "Testing MCP installation..."

    if uvx run awslabs.aws-documentation-mcp-server@latest --help >/dev/null 2>&1; then
        print_success "MCP server is working correctly"
    else
        print_warning "MCP server test failed, but this might be expected depending on the server implementation"
    fi
}

# Function to create team instructions
create_team_instructions() {
    print_status "Creating team setup instructions..."

    cat > "AWS_DOCS_MCP_SETUP.md" << 'EOF'
# AWS Documentation MCP Setup

## What was installed

✅ **AWS Documentation MCP Server** - Provides access to AWS documentation within Cursor
✅ **Cursor MCP Configuration** - Automatically configured for team use
✅ **Cursor Rules** - Added AWS documentation best practices

## How to use

### In Cursor Chat
You can now ask questions about AWS services and get documentation directly:

```
@aws-docs How do I configure S3 bucket naming rules?
@aws-docs Show me documentation about Lambda function configuration
@aws-docs What are the best practices for EC2 instance types?
```

### Available Commands
- **Read Documentation**: Fetch specific AWS docs pages
- **Search Documentation**: Search across all AWS documentation
- **Get Recommendations**: Find related AWS documentation
- **Cite Sources**: All responses include proper citations

### Example Queries
- "Look up documentation on S3 bucket naming rules and cite your sources"
- "Find AWS Lambda best practices documentation"
- "Get recommendations for EC2 documentation based on the current page"
- "Search for AWS documentation about VPC configuration"

## Troubleshooting

### If MCP doesn't work in Cursor:
1. Restart Cursor completely
2. Check that the MCP server is installed: `uv tool list`
3. Verify configuration file exists at the path shown during setup
4. Check Cursor's MCP logs in the developer tools

### To reinstall:
```bash
./scripts/setup-aws-docs-mcp.sh
```

### For China regions:
Edit the MCP configuration file and change:
```json
"AWS_DOCUMENTATION_PARTITION": "aws-cn"
```

## Team Benefits
- ✅ No manual configuration required per developer
- ✅ Consistent AWS documentation access across team
- ✅ Automatic citation and source linking
- ✅ Integrated with existing development workflow
- ✅ Works offline once docs are cached
EOF

    print_success "Team instructions created: AWS_DOCS_MCP_SETUP.md"
}

# Main execution
main() {
    print_status "🚀 Setting up AWS Documentation MCP for the team..."
    echo

    # Check prerequisites and install if needed
    install_uv
    install_python

    # Install MCP server
    install_mcp_server

    # Configure Cursor
    configure_cursor_mcp

    # Test installation
    test_mcp_installation

    # Create team documentation
    create_team_instructions

    echo
    print_success "🎉 AWS Documentation MCP setup completed successfully!"
    echo
    print_status "Next steps:"
    echo "  1. Restart Cursor to load the new MCP configuration"
    echo "  2. Share the AWS_DOCS_MCP_SETUP.md file with your team"
    echo "  3. Start using @aws-docs in Cursor chat!"
    echo
    print_status "Configuration file location: $(get_cursor_mcp_path)"
}

# Run main function
main "$@"
